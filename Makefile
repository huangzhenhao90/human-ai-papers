.PHONY: update build-data validate test web-build verify

update:
	python scripts/update_project.py

build-data:
	python scripts/build_unified_index.py

validate:
	python scripts/validate_release.py

test:
	pytest -q

web-build:
	cd web && npm run typecheck && npm run build

verify: test validate web-build
