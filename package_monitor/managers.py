from collections import namedtuple
import json

from importlib_metadata import distributions

from packaging.version import parse as version_parse
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import requests

from django.apps import apps as django_apps
from django.db import models, transaction

from allianceauth.services.hooks import get_extension_logger

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
)
from .utils import LoggerAddTag


logger = LoggerAddTag(get_extension_logger(__name__), __title__)
_DistributionInfo = namedtuple("_DistributionInfo", ["name", "files", "distribution"])


class DistributionManager(models.Manager):
    def outdated_count(self) -> int:
        """Returns the number of outdated distribution packages"""
        return self.filter(is_outdated=True).count()

    def update_all(self) -> int:
        """Updates the list of relevant distribution packages in the database"""
        packages = self._select_relevant_packages()
        requirements = self._compile_package_requirements(packages)
        self._fetch_versions_from_pypi(packages, requirements)
        self._save_packages(packages, requirements)
        return len(packages)

    @classmethod
    def _select_relevant_packages(cls) -> dict:
        """returns subset of distribution packages with packages of interest

        Interesting packages are related to installed apps or explicitely defined
        """

        def create_or_update_package(dist, packages: dict) -> None:
            if dist.name not in packages:
                requirements = (
                    [Requirement(r) for r in dist.distribution.requires]
                    if dist.distribution.requires
                    else list()
                )
                packages[dist.name] = {
                    "name": dist.name,
                    "apps": list(),
                    "current": version_parse(dist.distribution.version),
                    "requirements": requirements,
                    "distribution": dist.distribution,
                }

        packages = dict()
        for dist in cls._distribution_packages_amended():
            for app in django_apps.get_app_configs():
                my_file = app.module.__file__
                for dist_file in dist.files:
                    if my_file.endswith(dist_file):
                        create_or_update_package(dist, packages)
                        packages[dist.name]["apps"].append(app.name)
                        break

                if PACKAGE_MONITOR_SHOW_ALL_PACKAGES or (
                    PACKAGE_MONITOR_INCLUDE_PACKAGES
                    and dist.name in PACKAGE_MONITOR_INCLUDE_PACKAGES
                ):
                    create_or_update_package(dist, packages)

        return packages

    @staticmethod
    def _distribution_packages_amended() -> list:
        """returns the list of all known distribution packages with amended infos"""
        return [
            _DistributionInfo(
                name=dist.metadata["Name"].lower(),
                distribution=dist,
                files=[
                    "/" + str(f) for f in dist.files if str(f).endswith("__init__.py")
                ],
            )
            for dist in distributions()
        ]

    @staticmethod
    def _compile_package_requirements(packages: dict) -> dict:
        """returns all requirements in consolidated from all known distributions
        for given packages
        """
        requirements = dict()
        for dist in distributions():
            if dist.requires:
                for requirement in [Requirement(r) for r in dist.requires]:
                    requirement_name = requirement.name.lower()
                    if requirement_name in packages:
                        if requirement_name not in requirements:
                            requirements[requirement_name] = {
                                "specifier": SpecifierSet(),
                                "used_by": list(),
                            }

                        requirements[requirement_name]["used_by"].append(
                            dist.metadata["Name"]
                        )
                        if requirement.specifier:
                            requirements[requirement_name][
                                "specifier"
                            ] &= requirement.specifier

        return requirements

    @staticmethod
    def _fetch_versions_from_pypi(packages: dict, requirements: dict) -> None:
        """fetches the latest versions for given packages from PyPI in accordance
        with the given requirements and updates the packages
        """
        for package_name in packages:
            logger.info(
                f"Fetching info for distribution package '{package_name}' from PyPI"
            )
            r = requests.get(f"https://pypi.org/pypi/{package_name}/json")
            if r.status_code == requests.codes.ok:
                pypi_info = r.json()
                latest = None
                for release, _ in pypi_info["releases"].items():
                    my_release = version_parse(release)
                    if not my_release.is_prerelease:
                        if package_name in requirements:
                            is_valid = (
                                my_release in requirements[package_name]["specifier"]
                            )
                        else:
                            is_valid = True

                        if is_valid and (not latest or my_release > latest):
                            latest = my_release
            else:
                if r.status_code == 404:
                    logger.info(f"Package '{package_name}' is not registered in PyPI")
                else:
                    logger.warning(
                        "Failed to retrive infos from PyPI for "
                        f"package '{package_name}'. Status code: {r.status_code}, "
                        f"response: {r.content}"
                    )
                latest = None

            packages[package_name]["latest"] = latest

    def _save_packages(self, packages: dict, requirements: dict) -> None:
        """Saves the given package information into the model"""

        def metadata_value(dist, prop: str) -> str:
            return dist.metadata[prop] if dist.metadata[prop] != "UNKNOWN" else ""

        def metadata_value_2(packages: dict, name: str, prop: str) -> str:
            name = name.lower()
            return (
                metadata_value(packages[name]["distribution"], prop)
                if name in packages
                else ""
            )

        with transaction.atomic():
            self.all().delete()
            for package_name, package in packages.items():
                is_outdated = (
                    package["current"] < package["latest"]
                    if package["latest"]
                    else None
                )
                used_by = (
                    [
                        {
                            "name": package_name,
                            "homepage_url": metadata_value_2(
                                packages, package_name, "Home-page"
                            ),
                        }
                        for package_name in sorted(
                            list(set(requirements[package_name]["used_by"])),
                            key=str.casefold,
                        )
                    ]
                    if package_name in requirements
                    else []
                )

                self.create(
                    name=package["distribution"].metadata["Name"],
                    apps=json.dumps(sorted(package["apps"], key=str.casefold)),
                    used_by=json.dumps(used_by),
                    installed_version=str(package["current"]),
                    latest_version=str(package["latest"]) if package["latest"] else "",
                    is_outdated=is_outdated,
                    description=metadata_value(package["distribution"], "Summary"),
                    website_url=metadata_value(package["distribution"], "Home-page"),
                )
