dirs=/etc

for dir in $dirs; do
  if [ ! -d $dir/.git ]; then
    cd $dir
    git-init-db
    git-add .
    git-commit -m "Initial commit. Hoorah!"
    git-repack -a -d
  fi
done

