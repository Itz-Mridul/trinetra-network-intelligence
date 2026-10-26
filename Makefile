.PHONY: check calibration evaluate

check:
	python3 tests/test_smoke.py
	python3 -m compileall -q analysis pi_scripts dashboard
	@for f in pi_scripts/*.sh; do bash -n "$$f"; done
	@bash -n phone/termux_sender.sh
	@echo "All project checks passed."

calibration:
	python3 analysis/calibration.py --csv data/calibration/cal_data.csv

evaluate:
	python3 analysis/evaluate.py --features data/features.csv
