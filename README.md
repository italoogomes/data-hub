# MMarra Data Hub

**Repositório de Dados Inteligente** - MMarra Distribuidora Automotiva

---

## Objetivo

Plataforma que integra Sankhya ERP com interface web inteligente:

- 📊 **Dashboards** - Substituir Power BI
- 🤖 **Chat LLM** - Perguntas em linguagem natural
- 🔐 **Multi-usuário** - Acesso por permissões

---

## Como Funciona

```
Sankhya ERP → Azure Data Lake → Dashboards + Chat LLM
                                      ↑
                              knowledge/ (base de conhecimento)
```

A LLM aprende com a documentação em `knowledge/`:
- Estrutura das tabelas
- Processos de negócio
- Glossário de termos
- Regras de negócio
- Erros conhecidos

---

## Estrutura

```
mmarra-data-hub/
├── knowledge/              # LLM aprende aqui
│   ├── sankhya/tabelas/    # Schema
│   ├── processos/          # Fluxos
│   ├── glossario/          # Termos
│   ├── regras/             # Regras
│   └── erros/              # Problemas
├── queries/                # SQLs úteis
├── src/                    # Código
└── data/                   # Dados
```

---

## Quick Start

```bash
git clone https://github.com/italoogomes/mmarra-data-hub.git
cd mmarra-data-hub
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

## Autor

**Ítalo Gomes** - MMarra Distribuidora Automotiva

*Versão 3.0 - Fevereiro 2026*
