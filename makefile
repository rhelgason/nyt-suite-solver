setup: requirements.txt
	pip3 install -r requirements.txt

run:
	python3 src/main.py

clean:
	rm -rf __pycache__
