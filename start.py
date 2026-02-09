"""
MMarra Data Hub - Script de inicializacao
Inicia o servidor FastAPI + tunel ngrok em um comando.

Uso:
    python start.py
"""

import sys
import time
import subprocess
import httpx
import uvicorn


PORT = 8080
ngrok_process = None


def check_ollama():
    """Verifica se o Ollama esta rodando."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"[OK] Ollama rodando - {len(models)} modelo(s) disponivel(is)")
        return True
    except Exception:
        print("[AVISO] Ollama nao esta rodando!")
        print("[AVISO] Inicie o Ollama antes: ollama serve")
        print("[AVISO] Continuando mesmo assim...\n")
        return False


def kill_port(port):
    """Encerra processos usando a porta especificada."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True, timeout=5
                    )
                    print(f"[OK] Processo anterior na porta {port} encerrado (PID {pid})")
    except Exception:
        pass


def start_ngrok():
    """Inicia ngrok via subprocess e retorna a URL publica."""
    global ngrok_process

    # Matar ngrok anterior se existir
    try:
        subprocess.run(
            ["taskkill", "/IM", "ngrok.exe", "/F"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass

    time.sleep(1)

    # Iniciar ngrok como subprocess
    try:
        ngrok_process = subprocess.Popen(
            ["ngrok", "http", str(PORT), "--log", "stdout"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        print("[ERRO] ngrok nao encontrado no PATH.")
        print("[AVISO] Instale em https://ngrok.com/download")
        print(f"[AVISO] Servidor disponivel apenas em http://localhost:{PORT}\n")
        return None

    # Aguardar ngrok iniciar e consultar API local
    public_url = None
    for _ in range(10):
        time.sleep(1)
        try:
            r = httpx.get("http://localhost:4040/api/tunnels", timeout=3)
            tunnels = r.json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    public_url = t["public_url"]
                    break
            if not public_url and tunnels:
                public_url = tunnels[0].get("public_url")
            if public_url:
                break
        except Exception:
            continue

    if public_url:
        print("=" * 56)
        print("  MMarra Data Hub - Acesso Remoto")
        print("=" * 56)
        print(f"  Local:   http://localhost:{PORT}")
        print(f"  Publico: {public_url}")
        print("=" * 56)
        print(f"  Compartilhe a URL publica para acesso externo.")
        print(f"  Pressione Ctrl+C para encerrar.\n")
    else:
        print("[AVISO] ngrok iniciou mas nao retornou URL publica.")
        print("[AVISO] Verifique: http://localhost:4040")
        print(f"[AVISO] Servidor disponivel em http://localhost:{PORT}\n")

    return public_url


def main():
    print("\n--- MMarra Data Hub ---\n")

    # 1. Verificar Ollama
    check_ollama()

    # 2. Liberar porta se ocupada
    kill_port(PORT)

    # 3. Iniciar ngrok
    ngrok_url = start_ngrok()

    # 4. Iniciar FastAPI (bloqueia aqui)
    try:
        uvicorn.run(
            "src.api.app:app",
            host="0.0.0.0",
            port=PORT,
            reload=False,
            log_level="info",
        )
    except KeyboardInterrupt:
        pass
    finally:
        print("\nEncerrando...")
        if ngrok_process:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=5)
            print("[OK] Tunel ngrok encerrado.")
        print("[OK] Servidor encerrado.")


if __name__ == "__main__":
    main()
