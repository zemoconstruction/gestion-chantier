"""
Point d'entrée utilisé pour fabriquer le logiciel installable (.exe).
Démarre le serveur en arrière-plan et ouvre automatiquement le navigateur.
Double-cliquer sur l'exécutable suffit à utiliser le logiciel.
"""
import socket
import threading
import time
import webbrowser

from app import app, init_db, DB_PATH
import os


def port_is_busy(port=5000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(("localhost", port)) == 0
    finally:
        s.close()


def open_browser():
    time.sleep(1.3)
    webbrowser.open("http://localhost:5000")


def main():
    # Si le logiciel tourne déjà (lancé une 2e fois), on ouvre juste un nouvel onglet.
    if port_is_busy(5000):
        webbrowser.open("http://localhost:5000")
        return

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
    except ImportError:
        # secours si waitress n'est pas disponible
        app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
