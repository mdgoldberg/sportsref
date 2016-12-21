from setuptools import setup, find_packages

setup(name='sportsref',
      version='0.7.14',
      description='Scraping data from sports-reference.com and related sites',
      url='https://github.com/mdgoldberg/sportsref',
      author='Matt Goldberg',
      author_email='mgoldberg@college.harvard.edu',
      license='GNU GPLv3',
      packages=find_packages(),
      install_requires=[
          'appdirs',
          'numexpr',
          'numpy',
          'pandas',
          'pyquery',
          'requests',
          'scipy',
      ]
      )
