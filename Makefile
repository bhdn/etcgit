rpm:
	./setup.py bdist_rpm --requires python,git --no-autoreq \
		--post-install post-install.sh
