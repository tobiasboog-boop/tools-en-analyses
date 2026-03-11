from setuptools import setup, find_packages

setup(
    name='notifica-sdk',
    version='0.1.0',
    description='Python client voor de Notifica Data API',
    packages=find_packages(),
    python_requires='>=3.9',
    install_requires=[
        'requests>=2.28',
        'pandas>=1.5',
    ],
    extras_require={
        'dotenv': ['python-dotenv>=1.0'],
    },
)
