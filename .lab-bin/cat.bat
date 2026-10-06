@echo off
python -c "import sys; sys.stdout.write(open(sys.argv[1],'rb').read().decode('utf-8','replace'))" %*