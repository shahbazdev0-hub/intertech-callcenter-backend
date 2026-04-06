module.exports = {
  apps: [
    {
      name: 'venderia-celery-worker',
      script: '/var/www/kiven/backend/venv/bin/celery',
      args: '-A app.tasks.celery worker --loglevel=info --concurrency=4',
      cwd: '/var/www/kiven/backend',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: '/var/log/pm2/celery-worker-error.log',
      out_file: '/var/log/pm2/celery-worker-out.log'
    },
    {
      name: 'venderia-celery-beat',
      script: '/var/www/kiven/backend/venv/bin/celery',
      args: '-A app.tasks.celery beat --loglevel=info',
      cwd: '/var/www/kiven/backend',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      error_file: '/var/log/pm2/celery-beat-error.log',
      out_file: '/var/log/pm2/celery-beat-out.log'
    }
  ]
}
