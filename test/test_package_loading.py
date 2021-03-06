import pytest


@pytest.mark.parametrize('active_server', ['main', 'secondary'])
def test_load_from_url(selenium_standalone, web_server_secondary,
                       active_server):

    if active_server == 'secondary':
        url, port, log_main = web_server_secondary
        log_backup = selenium_standalone.server_log
    elif active_server == 'main':
        _, _, log_backup = web_server_secondary
        log_main = selenium_standalone.server_log
        url = selenium_standalone.server_hostname
        port = selenium_standalone.server_port
    else:
        raise AssertionError()

    with log_backup.open('r') as fh_backup, \
            log_main.open('r') as fh_main:

        # skip existing log lines
        fh_main.seek(0, 2)
        fh_backup.seek(0, 2)

        selenium_standalone.load_package(f"http://{url}:{port}/pyparsing.js")
        assert "Invalid package name or URI" not in selenium_standalone.logs

        # check that all ressources were loaded from the active server
        txt = fh_main.read()
        assert '"GET /pyparsing.js HTTP/1.1" 200' in txt
        assert '"GET /pyparsing.data HTTP/1.1" 200' in txt

        # no additional ressources were loaded from the other server
        assert len(fh_backup.read()) == 0

    selenium_standalone.run("from pyparsing import Word, alphas")
    selenium_standalone.run("Word(alphas).parseString('hello')")

    selenium_standalone.load_package(f"http://{url}:{port}/numpy.js")
    selenium_standalone.run("import numpy as np")


def test_list_loaded_urls(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package('pyparsing')
    assert selenium.run_js(
            'return Object.keys(pyodide.loadedPackages)') == ['pyparsing']
    assert selenium.run_js(
            "return pyodide.loadedPackages['pyparsing']") == "default channel"


def test_uri_mismatch(selenium_standalone):
    selenium_standalone.load_package('pyparsing')
    selenium_standalone.load_package('http://some_url/pyparsing.js')
    assert ("URI mismatch, attempting to load package pyparsing" in
            selenium_standalone.logs)
    assert "Invalid package name or URI" not in selenium_standalone.logs


def test_invalid_package_name(selenium):
    selenium.load_package('wrong name+$')
    assert "Invalid package name or URI" in selenium.logs
    selenium.clean_logs()

    selenium.load_package('tcp://some_url')
    assert "Invalid package name or URI" in selenium.logs


@pytest.mark.parametrize('packages', [['pyparsing', 'pytz'],
                                      ['pyparsing', 'matplotlib']],
                         ids='-'.join)
def test_load_packages_multiple(selenium_standalone, packages):
    selenium = selenium_standalone
    selenium.load_package(packages)
    selenium.run(f'import {packages[0]}')
    selenium.run(f'import {packages[1]}')
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f'Loading {packages[0]}') == 1
    assert selenium.logs.count(f'Loading {packages[1]}') == 1


@pytest.mark.parametrize('packages', [['pyparsing', 'pytz'],
                                      ['pyparsing', 'matplotlib']],
                         ids='-'.join)
def test_load_packages_sequential(selenium_standalone, packages):
    selenium = selenium_standalone
    promises = ','.join(
        'pyodide.loadPackage("{}")'.format(x) for x in packages
    )
    selenium.run_js(
        'window.done = false\n' +
        'Promise.all([{}])'.format(promises) +
        '.finally(function() { window.done = true; })')
    selenium.wait_until_packages_loaded()
    selenium.run(f'import {packages[0]}')
    selenium.run(f'import {packages[1]}')
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f'Loading {packages[0]}') == 1
    assert selenium.logs.count(f'Loading {packages[1]}') == 1


def test_load_handle_failure(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package('pytz')
    selenium.run('import pytz')
    selenium.load_package('pytz2')
    selenium.load_package('pyparsing')
    assert 'Loading pytz' in selenium.logs
    assert 'Loading pytz2' in selenium.logs
    assert "Unknown package 'pytz2'" in selenium.logs
    assert 'Loading pyparsing' in selenium.logs  # <- this fails
