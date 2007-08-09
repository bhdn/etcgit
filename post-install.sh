dirs=/etc
exclude=/usr/share/etcgit/exclude

for dir in $dirs; do
  if [ ! -d $dir/.git ]; then
    cd $dir
    git-init-db
    mkdir -p .git/info
    cp /usr/share/etcgit/exclude .git/info/exclude
    git-add .
    git-commit -m "Initial commit. Hoorah!"
    git-repack -a -d
  fi
done

