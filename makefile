install:
	pip install -e .

test:
	pytest tests/

run:
	python -m sudodev

clean:
	rm -rf build dist .pytest_cache
	find . -name "*.pyc" -delete