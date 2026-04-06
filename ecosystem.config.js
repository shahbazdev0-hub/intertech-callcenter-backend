module.exports = {
  apps: [{
    name: 'venderia-backend',
    script: '/var/www/kiven/backend/venv/bin/uvicorn',
    args: 'app.main:app --host 0.0.0.0 --port 8000',
    cwd: '/var/www/kiven/backend',
    interpreter: 'none',
    instances: 1,
    exec_mode: 'fork',
    env: {
      NODE_ENV: 'production'
    },
    error_file: '/var/log/pm2/venderia-backend-error.log',
    out_file: '/var/log/pm2/venderia-backend-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    autorestart: true,
    watch: false,
    max_memory_restart: '1G'
  }]
}
