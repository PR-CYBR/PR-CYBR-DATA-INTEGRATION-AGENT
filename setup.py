from setuptools import find_packages, setup


core_packages = find_packages(where='src')
script_packages = find_packages(where='.', include=['scripts', 'scripts.*'])
packages = list(dict.fromkeys(core_packages + script_packages))

with open('requirements.txt', encoding='utf-8') as requirements_file:
    requirements = [line.strip() for line in requirements_file if line.strip() and not line.startswith('#')]


setup(
    name='PR_CYBR_DATA_INTEGRATION_AGENT',
    version='0.1.0',
    packages=packages,
    package_dir={'': 'src', 'scripts': 'scripts'},
    install_requires=requirements,
    author='PR-CYBR',
    author_email='support@pr-cybr.com',
    description='PR-CYBR-DATA-INTEGRATION-AGENT',
    url='https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT',
)
