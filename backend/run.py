from backend import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=app.config.get('APP_HTTP_PORT', 5000))
