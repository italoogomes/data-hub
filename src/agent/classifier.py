"""
MMarra Data Hub - Classificador LLM.
Prompt de classificação + funções groq_classify, ollama_classify, llm_classify.
Extraído de smart_agent.py na refatoração modular.
"""

import re
import os
import json
import time
import asyncio
import requests as req_sync
from typing import Optional

from src.core.groq_client import (
    pool_classify, groq_request, GROQ_MODEL, GROQ_MODEL_CLASSIFY
)

# Config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", os.getenv("LLM_MODEL", "qwen3:4b"))
USE_LLM_CLASSIFIER = os.getenv("USE_LLM_CLASSIFIER", "true").lower() in ("true", "1", "yes")
LLM_CLASSIFIER_TIMEOUT = int(os.getenv("LLM_CLASSIFIER_TIMEOUT", "60"))


LLM_CLASSIFIER_PROMPT = """Voce e o interpretador de perguntas do sistema ERP da MMarra Distribuidora Automotiva.
Analise a pergunta do usuario e retorne APENAS um JSON (sem markdown, sem explicacao, sem texto antes ou depois).

# INTENTS POSSIVEIS
- pendencia_compras: pedidos de compra pendentes, o que falta chegar, entregas, previsoes
- estoque: quantidade em estoque, saldo, estoque critico, disponibilidade
- vendas: vendas, faturamento, notas fiscais de venda, receita
- produto: busca por produto especifico, codigo fabricante (HU711/51, WK950/21), similares, cross-reference, visao 360
- busca_produto: usuario quer ENCONTRAR/PROCURAR um produto por nome, codigo, referencia, aplicacao. Palavras-chave: "tem", "busca", "procura", "encontra", "acha", "existe", "onde tem". Diferente de pendencia (pedidos) e estoque (saldo).
- busca_cliente: usuario quer encontrar um CLIENTE por nome, CNPJ, cidade. Ex: "dados do cliente auto pecas", "clientes de uberlandia"
- busca_fornecedor: usuario quer encontrar um FORNECEDOR por nome, contato. Ex: "contato do fornecedor nakata", "telefone da mann filter"
- rastreio_pedido: o usuario quer RASTREAR um pedido de venda especifico por NUNOTA. Quer saber status, conferencia, separacao, se as pecas foram compradas, se chegou. Palavras-chave: "status do pedido", "como esta o pedido", "meu pedido", "pedido X", "conferencia", "separacao", "ja comprou", "ja chegou". IMPORTANTE: diferente de pendencia_compras (que e sobre pedidos de COMPRA pendentes). rastreio_pedido e sobre um pedido de VENDA especifico.
- conhecimento: como funcionam processos, regras, politicas, explicacoes do ERP
- saudacao: oi, bom dia, ola
- ajuda: o que voce faz, como funciona, help
- desconhecido: nao se encaixa em nenhum

# CAMPOS DO JSON
- intent: um dos intents acima
- marca: nome da marca mencionada (MAIUSCULO) ou null
- fornecedor: nome do fornecedor ou null
- empresa: nome da empresa/filial ou null
- comprador: nome do comprador ou null
- periodo: "hoje"|"ontem"|"semana"|"mes"|"ano" ou null
- view: "pedidos" (agrupado por pedido - padrao para "qual pedido") ou "itens" (produtos individuais - para "qual item/produto")
- filtro: objeto com instrucoes de filtragem ou null (ver abaixo)
- ordenar: campo para ordenar + _DESC ou _ASC (ver campos abaixo)
- top: numero de resultados desejados ou null (ex: 1 para "qual o...", 5 para "top 5")
- tipo_compra: "casada"|"estoque" ou null (tipo de compra mencionado - casada=empenho/vinculada, estoque=reposicao/entrega futura)
- aplicacao: veiculo/motor/maquina mencionado para busca por aplicacao ou null (ex: "SCANIA R450", "MERCEDES ACTROS", "MOTOR DC13")
- texto_busca: texto livre que o usuario quer buscar (nome do produto, nome do cliente, etc.) ou null. Usado com busca_produto/busca_cliente/busca_fornecedor.
- nunota: numero unico da nota/pedido (NUNOTA) quando o usuario menciona um numero de pedido de venda. Extrair o numero da pergunta. Ex: "pedido 1199868" → nunota=1199868. Usado com rastreio_pedido.
- extra_columns: lista de colunas extras que o usuario quer ver no relatorio, ou null
  Colunas possiveis: "EMPRESA", "TIPO_COMPRA", "COMPRADOR", "PREVISAO_ENTREGA", "CONFIRMADO",
  "FORNECEDOR", "UNIDADE", "QTD_PEDIDA", "QTD_ATENDIDA", "VLR_UNITARIO", "DIAS_ABERTO",
  "NUM_FABRICANTE", "NUM_ORIGINAL", "REFERENCIA", "APLICACAO"
  Detecte quando o usuario pede para ADICIONAR/VER campos com frases como:
  "contendo X", "com o campo X", "incluindo X", "mostrando X",
  "precisa ter X", "quero ver X tambem", "adiciona X"
  Mapeamentos importantes:
  "codigo fabricante"/"numero fabricante"/"ref fabricante"/"fabricante" = "NUM_FABRICANTE"
  "numero original"/"original" = "NUM_ORIGINAL"
  "referencia"/"ref interna" = "REFERENCIA"
  "previsao"/"previsao de entrega"/"quando chega" = "PREVISAO_ENTREGA"
  "tipo de compra"/"casada ou estoque" = "TIPO_COMPRA"
  "dias"/"dias aberto"/"dias pendente" = "DIAS_ABERTO"
  "comprador"/"quem compra" = "COMPRADOR"
  "empresa"/"filial" = "EMPRESA"
  Se o usuario NAO pediu colunas extras, retorne null.

# FILTRO - como interpretar pedidos de filtragem
O campo "filtro" permite filtrar os dados retornados. Formato: {"campo": "NOME_DO_CAMPO", "operador": "tipo", "valor": "X"}

Operadores:
- "igual": campo == valor (ex: STATUS_ENTREGA == "ATRASADO")
- "vazio": campo esta vazio/nulo (ex: PREVISAO_ENTREGA sem data)
- "nao_vazio": campo tem valor preenchido
- "maior": campo > valor (numerico)
- "menor": campo < valor (numerico)
- "contem": campo contem texto

# CAMPOS DISPONIVEIS (pendencia_compras) - ATENCAO AOS NOMES:
- PEDIDO: numero do pedido de compra
- DT_PEDIDO: data em que o pedido foi feito (quando compramos)
- PREVISAO_ENTREGA: data prevista para o fornecedor entregar (quando vai chegar)
- CONFIRMADO: se o fornecedor confirmou (S/N)
- STATUS_ENTREGA: situacao da entrega (ATRASADO/NO PRAZO/PROXIMO/SEM PREVISAO)
- DIAS_ABERTO: quantos dias o pedido esta em aberto sem receber
- VLR_PENDENTE: valor em reais do que falta receber
- QTD_PENDENTE: quantidade de pecas que falta receber
- FORNECEDOR, CODPROD, PRODUTO, MARCA, QTD_PEDIDA, VLR_UNITARIO, EMPRESA, COMPRADOR
- TIPO_COMPRA: tipo do pedido de compra ("Casada" = empenho/vinculada a venda, "Estoque" = reposicao geral)
- NUM_FABRICANTE: codigo que o fabricante da a peca (AD_NUMFABRICANTE)
- NUM_ORIGINAL: numero original da peca (AD_NUMORIGINAL)
- REFERENCIA: referencia interna do cadastro (PRO.REFERENCIA)

IMPORTANTE - Diferencie corretamente:
- "data de entrega" / "previsao de entrega" / "quando vai chegar" = PREVISAO_ENTREGA (NAO e DT_PEDIDO!)
- "data do pedido" / "quando foi pedido" / "quando comprou" = DT_PEDIDO
- "mais atrasado" / "mais tempo aberto" = DIAS_ABERTO_DESC
- "mais caro" / "maior valor" = VLR_PENDENTE_DESC

Campos para estoque: CODPROD, PRODUTO, MARCA, ESTOQUE_TOTAL, ESTOQUE_MINIMO, CUSTO_MEDIO
Campos para vendas: NUNOTA, CLIENTE, PRODUTO, QTD, VLR_TOTAL, DT_VENDA

# CONTEXTO DE CONVERSA
Se houver contexto da conversa anterior (adicionado ao final do prompt), use-o para interpretar a pergunta corretamente.
Exemplos de referencias ao contexto:
- "me passa os atrasados" = filtrar STATUS_ENTREGA="ATRASADO" dos dados anteriores
- "e os de estoque?" = manter marca/empresa anterior, filtrar TIPO_COMPRA="Estoque"
- "agora por itens" = mesma consulta anterior mas view="itens"
- "os 41 atrasados" = 41 e a QUANTIDADE de itens atrasados mencionada antes, filtrar STATUS_ENTREGA="ATRASADO"
- "qual o mais caro?" = referencia aos dados anteriores, ordenar VLR_PENDENTE_DESC + top 1
IMPORTANTE: Quando o usuario menciona um NUMERO que coincide com dados da conversa anterior
(ex: "41 atrasados" quando havia exatamente 41 itens com STATUS=ATRASADO), trate como
filtro de STATUS, NAO como filtro de DIAS_ABERTO ou outro campo numerico.

# EXEMPLOS
Pergunta: "o que falta chegar da mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual pedido esta sem previsao de entrega da tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"PREVISAO_ENTREGA","operador":"vazio","valor":null},"ordenar":null,"top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pedidos atrasados da Donaldson"
{"intent":"pendencia_compras","marca":"DONALDSON","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual pedido da sabo tem a maior previsao de entrega?"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"PREVISAO_ENTREGA_DESC","top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual pedido da mann foi feito mais recentemente?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"DT_PEDIDO_DESC","top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual o pedido mais caro da Mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"VLR_PENDENTE_DESC","top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "quais pedidos estao confirmados?"
{"intent":"pendencia_compras","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"CONFIRMADO","operador":"igual","valor":"S"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual item com maior quantidade pendente da Tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":"QTD_PENDENTE_DESC","top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "tem algum pedido acima de 50 mil reais?"
{"intent":"pendencia_compras","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"VLR_PENDENTE","operador":"maior","valor":"50000"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "vendas de hoje"
{"intent":"vendas","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":"hoje","view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "como funciona a compra casada?"
{"intent":"conhecimento","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "quais pedidos casados da sabo?"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"TIPO_COMPRA","operador":"igual","valor":"Casada"},"ordenar":null,"top":null,"tipo_compra":"casada","aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "quem compra a marca mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "quem fornece a marca sabo?"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pedidos de empenho atrasados"
{"intent":"pendencia_compras","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null,"tipo_compra":"casada","aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "compras de estoque da eaton"
{"intent":"pendencia_compras","marca":"EATON","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"TIPO_COMPRA","operador":"igual","valor":"Estoque"},"ordenar":null,"top":null,"tipo_compra":"estoque","aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pendencias da Nakata por Ribeirao Preto"
{"intent":"pendencia_compras","marca":"NAKATA","fornecedor":null,"empresa":"RIBEIR","comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "estoque em Uberlandia"
{"intent":"estoque","marca":null,"fornecedor":null,"empresa":"UBERL","comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "vendas de hoje em Itumbiara"
{"intent":"vendas","marca":null,"fornecedor":null,"empresa":"ITUMBI","comprador":null,"periodo":"hoje","view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "HU711/51"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "tudo sobre o produto 133346"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "similares do produto 133346"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "quem tem o filtro WK 950/21"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pecas para scania r450"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"SCANIA R450","texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual filtro serve no mercedes actros"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"MERCEDES ACTROS","texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "filtros mann para motor dc13"
{"intent":"produto","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"MOTOR DC13","texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pendencias da nakata por ribeirao contendo codigo do fabricante"
{"intent":"pendencia_compras","marca":"NAKATA","fornecedor":null,"empresa":"RIBEIR","comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":["NUM_FABRICANTE"]}

Pergunta: "itens pendentes da mann mostrando empresa e previsao"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":["EMPRESA","PREVISAO_ENTREGA"]}

Pergunta: "pendencias da sabo com comprador e tipo de compra"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":["COMPRADOR","TIPO_COMPRA"]}

Pergunta: "me traga as pendencias da nakata incluindo referencia do fabricante e dias em aberto"
{"intent":"pendencia_compras","marca":"NAKATA","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":["NUM_FABRICANTE","DIAS_ABERTO"]}

Pergunta: "tem filtro de ar da mann pra scania?"
{"intent":"busca_produto","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"SCANIA","texto_busca":"filtro de ar","nunota":null,"extra_columns":null}

Pergunta: "busca o RS5362"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"RS5362","nunota":null,"extra_columns":null}

Pergunta: "procura pecas pra volvo fh"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"VOLVO FH","texto_busca":"pecas","nunota":null,"extra_columns":null}

Pergunta: "preciso de todos os produto de filtro de ar"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"filtro de ar","nunota":null,"extra_columns":null}

Pergunta: "me traga todos os filtros de ar cadastrado no sistema"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"filtro de ar","nunota":null,"extra_columns":null}

Pergunta: "qual o codigo do produto ABRACADEIRA ACCUSEAL 127MM INOX"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"ABRACADEIRA ACCUSEAL 127MM INOX","nunota":null,"extra_columns":null}

Pergunta: "quais correias temos cadastradas"
{"intent":"busca_produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"correia","nunota":null,"extra_columns":null}

Pergunta: "me lista os produtos da marca wix"
{"intent":"busca_produto","marca":"WIX","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "dados do cliente auto pecas ribeirao preto"
{"intent":"busca_cliente","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"auto pecas ribeirao preto","nunota":null,"extra_columns":null}

Pergunta: "qual o cnpj da empresa transportadora sul"
{"intent":"busca_cliente","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"transportadora sul","nunota":null,"extra_columns":null}

Pergunta: "telefone do fornecedor nakata"
{"intent":"busca_fornecedor","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"nakata","nunota":null,"extra_columns":null}

Pergunta: "contato da mann filter"
{"intent":"busca_fornecedor","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":"mann filter","nunota":null,"extra_columns":null}

Pergunta: "como esta o pedido 1199868?"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":1199868,"extra_columns":null}

Pergunta: "status do pedido 1199868, ele ja foi comprado?"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":1199868,"extra_columns":null}

Pergunta: "o pedido 5000 ta na conferencia?"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":5000,"extra_columns":null}

Pergunta: "meus pedidos pendentes de venda"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "ja chegou as pecas do pedido 6500?"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":6500,"extra_columns":null}

Pergunta: "quando vai chegar a peca do meu pedido 8000?"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":8000,"extra_columns":null}

# EXEMPLOS COM CONTEXTO (quando ha conversa anterior anexada ao final)

Contexto: pendencia_compras, marca=DONALDSON, 116 itens (ATRASADO: 41, NO PRAZO: 55, PROXIMO: 20)
Pergunta: "me passa os 41 atrasados"
{"intent":"pendencia_compras","marca":"DONALDSON","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Contexto: pendencia_compras, marca=NAKATA, empresa=RIBEIR, 13 itens
Pergunta: "e os atrasados?"
{"intent":"pendencia_compras","marca":"NAKATA","fornecedor":null,"empresa":"RIBEIR","comprador":null,"periodo":null,"view":"itens","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Contexto: pendencia_compras, marca=MANN, 85 itens, media 22 dias
Pergunta: "qual o pedido mais caro?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"VLR_PENDENTE_DESC","top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Contexto: pendencia_compras, marca=SABO, 50 itens (ATRASADO: 15, SEM PREVISAO: 8)
Pergunta: "quais estao sem previsao?"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":{"campo":"PREVISAO_ENTREGA","operador":"vazio","valor":null},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Agora classifique:
Pergunta: "{question}"
"""

def _build_context_hint(ctx) -> str:
    """Monta resumo curto do contexto da conversa para o classificador LLM.
    Retorna string vazia se nao ha contexto relevante."""
    if not ctx or not ctx.intent or ctx.turn_count == 0:
        return ""

    parts = []
    parts.append(f"Consulta anterior: {ctx.intent}")

    # Parametros ativos
    active_params = {k: v for k, v in ctx.params.items() if v}
    if active_params:
        param_str = ", ".join(f"{k}={v}" for k, v in active_params.items())
        parts.append(f"Filtros ativos: {param_str}")

    # Resumo dos resultados anteriores (contagens, nao dados brutos)
    if ctx.last_result and ctx.last_result.get("detail_data"):
        data = ctx.last_result["detail_data"]
        total_itens = len(data)
        status_count = {}
        for item in data:
            if isinstance(item, dict):
                st = item.get("STATUS_ENTREGA", "?")
                status_count[st] = status_count.get(st, 0) + 1
        if status_count:
            status_str = ", ".join(f"{k}: {v}" for k, v in sorted(status_count.items(), key=lambda x: -x[1]))
            parts.append(f"Resultado anterior: {total_itens} itens ({status_str})")
        else:
            parts.append(f"Resultado anterior: {total_itens} itens")

    # Descricao do resultado
    if ctx.last_result and ctx.last_result.get("description"):
        parts.append(f"Descricao: {ctx.last_result['description']}")

    # Pergunta anterior
    if ctx.last_question:
        parts.append(f"Pergunta anterior: \"{ctx.last_question}\"")

    return "\n".join(parts)


async def groq_classify(question: str, context_hint: str = "", model: str = None) -> Optional[dict]:
    """Classifica pergunta via Groq usando pool_classify."""
    if not pool_classify.available:
        return None

    prompt = LLM_CLASSIFIER_PROMPT.replace("{question}", question.replace('"', '\\"'))
    if context_hint:
        prompt += f"\n\n# CONTEXTO DA CONVERSA ANTERIOR (use para interpretar referencias):\n{context_hint}"

    _model = model or GROQ_MODEL
    result = await groq_request(
        pool=pool_classify,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=400,
        model=_model,
    )

    if not result:
        return None

    content = result["content"].strip()

    # Limpar thinking leak e markdown
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    # Extrair JSON da resposta
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', content)
    if not json_match:
        print(f"[GROQ:classify] JSON nao encontrado: {content[:150]}")
        return None

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        print(f"[GROQ:classify] JSON invalido: {content[:100]}")
        return None

    _model_short = _model.split("-")[-1] if "-" in _model else _model  # "70b-versatile" → "versatile"
    print(f"[GROQ:classify:{_model_short}] {parsed.get('intent')} | extra_cols={parsed.get('extra_columns')}")

    # Normalizar entidades para MAIUSCULO
    for key in ["marca", "fornecedor", "empresa", "comprador", "aplicacao"]:
        if parsed.get(key):
            parsed[key] = parsed[key].upper().strip()

    return parsed


async def ollama_classify(question: str, context_hint: str = "") -> Optional[dict]:
    """Fallback: Ollama local para classificar. Mais lento mas funciona offline."""
    prompt = LLM_CLASSIFIER_PROMPT.replace("{question}", question.replace('"', '\\"'))
    if context_hint:
        prompt += f"\n\n# CONTEXTO DA CONVERSA ANTERIOR (use para interpretar referencias):\n{context_hint}"

    def _call():
        return req_sync.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_CLASSIFIER_MODEL,
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"},
                ],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 200, "top_p": 0.1},
            },
            timeout=LLM_CLASSIFIER_TIMEOUT,
        )

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(_call)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"[OLLAMA-CLS] Erro HTTP {resp.status_code} ({elapsed:.1f}s)")
            return None

        data = resp.json()
        raw = data.get("message", {}).get("content", "").strip()
        raw = "{" + raw  # Prefixo assistant era "{"

        # Limpar thinking leak
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

        # Extrair JSON
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', raw)
        if not json_match:
            print(f"[OLLAMA-CLS] JSON nao encontrado ({elapsed:.1f}s): {raw[:100]}")
            return None

        result = json.loads(json_match.group())
        print(f"[OLLAMA-CLS] OK ({elapsed:.1f}s): {result}")

        for key in ["marca", "fornecedor", "empresa", "comprador"]:
            if result.get(key):
                result[key] = result[key].upper().strip()

        return result

    except req_sync.exceptions.Timeout:
        print(f"[OLLAMA-CLS] Timeout ({LLM_CLASSIFIER_TIMEOUT}s)")
        return None
    except req_sync.exceptions.ConnectionError:
        print(f"[OLLAMA-CLS] Ollama nao acessivel em {OLLAMA_URL}")
        return None
    except json.JSONDecodeError as e:
        print(f"[OLLAMA-CLS] JSON invalido: {e}")
        return None
    except Exception as e:
        print(f"[OLLAMA-CLS] Erro: {type(e).__name__}: {e}")
        return None


async def llm_classify(question: str, context_hint: str = "") -> Optional[dict]:
    """Classificador inteligente: Groq 70b (forte) -> Groq 8b (rapido) -> Ollama (local) -> None."""
    if not USE_LLM_CLASSIFIER:
        return None

    if pool_classify.available:
        # 1) Tentar modelo forte (70b) — melhor classificacao, 1000 req/dia gratis
        if GROQ_MODEL_CLASSIFY != GROQ_MODEL:
            result = await groq_classify(question, context_hint, model=GROQ_MODEL_CLASSIFY)
            if result:
                return result
            print(f"[LLM-CLS] {GROQ_MODEL_CLASSIFY} falhou, tentando {GROQ_MODEL}...")

        # 2) Fallback: modelo rapido (8b) — 14.400 req/dia gratis
        result = await groq_classify(question, context_hint, model=GROQ_MODEL)
        if result:
            return result
        print("[LLM-CLS] Groq falhou, tentando Ollama...")

    # 3) Fallback: Ollama local
    result = await ollama_classify(question, context_hint)
    return result


# ============================================================
