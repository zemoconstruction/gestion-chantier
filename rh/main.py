"""Point d'entrée du logiciel installé : démarre le serveur et ouvre le navigateur."""
import os
import socket
import threading
import time
import webbrowser

from app import app, init_db

PORT = int(os.environ.get("PORT", 5001))


def busy():
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", PORT)) == 0
    finally:
        s.close()


def main():
    if busy():                       # déjà lancé : on ouvre juste un onglet
        webbrowser.open(f"http://localhost:{PORT}")
        return
    init_db()
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://localhost:{PORT}")), daemon=True).start()
    from waitress import serve
    serve(app, host="127.0.0.1" if os.environ.get("LOCAL_ONLY") else "0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
