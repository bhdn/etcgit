rpm:
	./setup.py bdist_rpm --requires python,git-core --no-autoreq \
		--post-install post-install.sh
