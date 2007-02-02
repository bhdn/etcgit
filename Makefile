rpm:
	./setup.py bdist_rpm --requires python,/usr/bin/git --no-autoreq \
		--post-install post-install.sh
