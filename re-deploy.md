cd ~/projects/kibegi/api

source .venv/bin/activate

git pull origin main

pip install -r requirements.txt

python manage.py migrate

python manage.py collectstatic --noinput

sudo systemctl restart kibegi