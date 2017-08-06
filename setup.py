from distutils.core import setup

setup(
    name='blobstash-docstore',
    version='0.0.1',
    description='BlobStash DocStore client',
    author='Thomas Sileo',
    author_email='t@a4.io',
    url='https://github.com/tsileo/blobstash-python-docstore',
    packages=['blobstash.docstore'],
    license='MIT',
    install_requires=[
        'requests',
    ],
)
