devtest: ## Run all tests except the ones that require real requests
	@pytest --deselect="tests/test_auth.py::test_login"
