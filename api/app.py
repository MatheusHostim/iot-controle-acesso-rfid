from datetime import datetime
from pathlib import Path
from threading import Lock
import json
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
ARQUIVO = Path(__file__).resolve().parent / "acessos.json"
LOCK = Lock()

HTML = '''<!doctype html><html lang="pt-br"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CP03 IoT | Dashboard</title><style>body{font-family:system-ui;background:#10121a;color:#eef2ff;margin:35px auto;max-width:1000px;padding:0 16px}h1{color:#ff1767}a{color:#9cc7ff}table{width:100%;border-collapse:collapse;background:#1a2030}th,td{padding:12px;border-bottom:1px solid #30394b;text-align:left}th{color:#a8b2c8}.ok{color:#4be0a2}.bad{color:#ff8d96}.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}.card{background:#1a2030;border-radius:12px;padding:16px;min-width:160px}.card strong{font-size:30px;display:block}</style><h1>CP03 • Controle de Acesso IoT</h1><p>RFID + HC-SR04 → ESP32 → MQTT → Node-RED → Flask → JSON</p><div class="cards"><div class="card">Tentativas<strong id="total">0</strong></div><div class="card">Permitidas<strong id="permitidos">0</strong></div><div class="card">Negadas<strong id="negados">0</strong></div></div><table><thead><tr><th>Data</th><th>Hora</th><th>Cartão</th><th>Distância</th><th>Resultado</th></tr></thead><tbody id="linhas"></tbody></table><p><a href="/acessos">Ver JSON</a></p><script>async function atualizar(){try{const r=await fetch('/acessos');const d=await r.json();document.getElementById('total').textContent=d.length;document.getElementById('permitidos').textContent=d.filter(x=>x.resultado==='PERMITIDO').length;document.getElementById('negados').textContent=d.filter(x=>x.resultado==='NEGADO').length;document.getElementById('linhas').innerHTML=d.slice().reverse().map(x=>`<tr><td>${esc(x.data)}</td><td>${esc(x.hora)}</td><td>${esc(x.cartao_id)}</td><td>${x.distancia_cm===null?'Erro':x.distancia_cm+' cm'}</td><td class="${x.resultado==='PERMITIDO'?'ok':'bad'}">${esc(x.resultado)}</td></tr>`).join('')||'<tr><td colspan="5">Nenhum acesso registrado ainda.</td></tr>'}catch(e){console.error(e)}}function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}atualizar();setInterval(atualizar,3000)</script></html>'''

def carregar():
    if not ARQUIVO.exists():
        return []
    try:
        data = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []

@app.get("/")
def dashboard():
    return render_template_string(HTML)

@app.get("/acessos")
def listar():
    with LOCK:
        return jsonify(carregar())

@app.post("/acessos")
def registrar():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(erro="JSON invalido"), 400
    uid = dados.get("cartao_id")
    distancia = dados.get("distancia_cm")
    resultado = dados.get("resultado")
    if not isinstance(uid, str) or not uid or resultado not in ("PERMITIDO", "NEGADO"):
        return jsonify(erro="cartao_id/resultado invalidos"), 400
    if distancia is not None and (not isinstance(distancia, (int, float)) or isinstance(distancia, bool)):
        return jsonify(erro="distancia_cm invalida"), 400
    agora = datetime.now().astimezone()
    registro = {"cartao_id": uid, "distancia_cm": distancia, "data": agora.strftime("%d/%m/%Y"), "hora": agora.strftime("%H:%M:%S"), "resultado": resultado}
    with LOCK:
        registros = carregar()
        registros.append(registro)
        ARQUIVO.write_text(json.dumps(registros, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify(registro), 201

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
