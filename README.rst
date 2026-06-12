.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/qa4sm-autoreports.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/qa4sm-autoreports
    .. image:: https://readthedocs.org/projects/qa4sm-autoreports/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://qa4sm-autoreports.readthedocs.io/en/stable/
    .. image:: https://img.shields.io/coveralls/github/<USER>/qa4sm-autoreports/main.svg
        :alt: Coveralls
        :target: https://coveralls.io/r/<USER>/qa4sm-autoreports
    .. image:: https://img.shields.io/pypi/v/qa4sm-autoreports.svg
        :alt: PyPI-Server
        :target: https://pypi.org/project/qa4sm-autoreports/
    .. image:: https://img.shields.io/conda/vn/conda-forge/qa4sm-autoreports.svg
        :alt: Conda-Forge
        :target: https://anaconda.org/conda-forge/qa4sm-autoreports
    .. image:: https://pepy.tech/badge/qa4sm-autoreports/month
        :alt: Monthly Downloads
        :target: https://pepy.tech/project/qa4sm-autoreports
    .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
        :alt: Twitter
        :target: https://twitter.com/qa4sm-autoreports

.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

|

============
qa4sm-autoreports
============


    Add a short description here!


In order to compile latex to pdf reports, you need to install texlive from
https://tug.org/texlive/. This should enable the command line program `pdflatex`
which is called from some python functions in this package.

   sudo apt install texlive-full

pdflatex

Test will create a connection to test.qa4sm.eu. Therefore you must either
- have the .qa4smapirc set up locally or
- set the QA4SM_INSTANCE and QA4SM_TOKEN environment variables

.. _pyscaffold-notes:

Note
====

This project has been set up using PyScaffold 4.6. For details and usage
information on PyScaffold see https://pyscaffold.org/.
