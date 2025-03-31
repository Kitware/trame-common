# trame-common: common code for any trame package

Trame is rapidly evolving and having a dependency-less package to provide helper
functions and classes across trame's eco-system is important for its future
health. Initially some of those classes were created inside **trame-client**,
**trame-server** or even **trame**, but we reached a point where some of those
should become even more mainstream so they could easily be used on server,
client, widget and more. That is where **trame-common** comes to play by
providing a central location that any package can depend on. By default,
**trame** remain the meta package that will impose some minimum version on
**trame-common**, **trame-client** and **trame-server** and expose via some
common namespace various pieces of those 3 dependencies. But if you need any
piece of **trame-common**, feel free to depend on it.

Trame-common is not meant to be installed by itself, but instead be used by any
trame package that may require one of its function or helper class. While some
of the module may require extra dependency, we are not listing them in this
package purposely but the using code, should properly describe such dependency.

## Content

**trame-common** is composed of several packages to split the current set of
classes and function in meaningful groups.

- **trame_common.assets**: Contains anything related to local and remote file
  including possible associated mime types.
- **trame_common.decorators**: Contains all decorators for functions, classes
  and methods.
- **trame_common.exec**: Contains helpers for handling code execution (i.e.
  async, throttle, debounce, thread, process).
- **trame_common.obj**: Contains helpers for common trame objects (i.e.
  Component, App, Widget, Singleton)
- **trame_common.utils**: Contains utility functions.

## License

trame-common is made available under the Apache License, Version 2.0. For more
details, see
[LICENSE](https://github.com/Kitware/trame-common/blob/master/LICENSE).

## Development steps

- Clone the repository using `git clone`
- Install pre-commit via `pip install pre-commit` or `pip install -e ".[dev]"`
- Run `pre-commit install` to set up pre-commit hooks
- Run `pre-commit install --hook-type commit-msg` to register commit-msg hook
- Make changes to the code, and commit your changes to a separate branch. Use
  [conventional commit messages](https://www.conventionalcommits.org/en/v1.0.0/).
- Create a fork of the repository on GitHub
- Push your branch to your fork, and open a pull request

**Tips**

- When first creating a new project, it is helpful to run
  `pre-commit run --all-files` to ensure all files pass the pre-commit checks.
- A quick way to fix `ruff` issues is by installing ruff (`pip install ruff`)
  and running the `ruff check --fix .` or `ruff format` command at the root of
  your repository.
- A quick way to fix `codespell` issues is by installing codespell
  (`pip install codespell`) and running the `codespell -w` command at the root
  of your directory.
- The
  `.codespellrc file <https://github.com/codespell-project/codespell#using-a-config-file>`\_
  can be used fix any other codespell issues, such as ignoring certain files,
  directories, words, or regular expressions.
