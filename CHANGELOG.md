# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

### Added

### Changed

### Fixed

## [1.2.0] - 2021-07-20

### Changed

- Removed support for Django 2
- Add isort to CI
- Integrated allianceauth-app-utils

### Fixed

- Fix "Column 'website_url' cannot be null" (#5)

## [1.1.0] - 2020-11-11

### Added

- Shows the effective requirements of packages under "Used By" as tool tip [#1](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/1)

### Fixed

- KeyError: 'latest': [#2](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/2)

## [1.0.1] - 2020-11-05

### Fixed

- Spinner optimizes for light/dark mode
- Does no longer show vertical slider on full page
- Does no longer try to process distribution packages that have no name
- Fix white spaces and EOF in all files

## [1.0.0] - 2020-10-24

### Changed

- Will now show "update available" tab as default if there are updates
- Improved styling
- Improved text matrix

## [1.0.0b2] - 2020-09-22

### Changed

- Removed dependency conflict with Auth and Django 3

### Fixed

- Did not always recognize packages with capitals correctly (e.g. "Django").

## [1.0.0b1] - 2020-09-16

### Important Note for alpha users

Users of the alpha release will need to "migrate zero" their old installation before installing the beta version, because the migrations have been recreated from scratch for the beta.

### Added

- Initial beta release
