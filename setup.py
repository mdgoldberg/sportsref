from setuptools import setup, find_packages

setup(name='sportsref',
      version='0.8.1',
      description='Scraping data from sports-reference.com and related sites',
      url='https://github.com/mdgoldberg/sportsref',
      author='Matt Goldberg',
      author_email='mgoldberg@college.harvard.edu',
      packages=find_packages(),
      install_requires=[
          'appdirs',
          'boltons',
          'future',
          'mementos',
          'numexpr',
          'numpy',
          'pandas',
          'pyquery',
          'requests',
          'scipy',
      ]
      )
