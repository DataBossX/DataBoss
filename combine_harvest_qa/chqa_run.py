#!/usr/bin/env python3
"""Entry point: python3 chqa_run.py <command> ...   (see README.md)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chqa.cli import main
sys.exit(main())
