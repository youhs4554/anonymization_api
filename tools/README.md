# PET_anonymization

PET_anonymization toolkit instruction

## Installation

```
# clone repository
git clone https://github.com/youhs4554/PET_anonymization.git

# cd to root path
cd PET_anonymization

# using Anaconda is recommended
conda create -n env python=3.6

# activate env
conda activate env

# install required packages
pip install -r requirements.txt
```

## Usage

```
# cheat help docs
python run.py --help

# example cmd
python run.py --INPUT_ROOT /path/to/DCM_ROOT
              --ANONYM_DCM_ROOT /path/to/ANONYM_DCM_TOOT
              --VERBOSE
```
