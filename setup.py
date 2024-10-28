from os import path

from setuptools import find_packages, setup

# Get current directory
here = path.abspath(path.dirname(__file__))


# Read requirements from requirements.txt
def get_requirements():
    requirements = []
    try:
        with open(path.join(here, "requirements.txt"), encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print("Warning: requirements.txt not found")
    return requirements


# Read README for long description
def get_long_description():
    try:
        with open(path.join(here, "README.md"), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


setup(
    name="minion",  # Replace with your package name
    version="0.1.0",
    description="A short description of your package",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="femto",
    author_email="femtowin@gmail",
    # Project URLs
    url="https://github.com/femto/minion",
    # Find packages automatically
    packages=find_packages(exclude=["tests*"]),
    # Include non-Python files from MANIFEST.in
    include_package_data=True,
    # Project dependencies
    install_requires=get_requirements(),
    # Python version requirement
    python_requires=">=3.8",
    # Classifiers help users find your project
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "minion=minion.cli:app",
        ],
    },
    # Keywords for PyPI
    keywords="development, setup",
)
