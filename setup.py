from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='blobstash-docstore',
    version='0.1.0',
    description='BlobStash DocStore client',
    long_description=long_description,
    author='Thomas Sileo',
    author_email='t@a4.io',
    url='https://github.com/tsileo/blobstash-python-docstore',
    packages=['blobstash.docstore'],
    license='MIT',
    install_requires=[
        'blobstash-base==0.1.0',
        'blobstash-filetree==0.1.0',
        'requests',
        'jsonpatch',
    ],
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='blobstash DocStore client JSON Lua document store',
)
