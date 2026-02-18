"""
MMarra Data Hub - Elasticsearch Index Mappings
Definicao dos indices: produtos (400k+) e parceiros (100k+).
"""

PRODUCTS_INDEX = "idx_produtos"
PARTNERS_INDEX = "idx_parceiros"

PRODUCTS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "brazilian": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "brazilian_stem", "asciifolding"]
                },
                "code_analyzer": {
                    "type": "custom",
                    "tokenizer": "keyword",
                    "filter": ["lowercase", "code_strip"]
                }
            },
            "filter": {
                "brazilian_stem": {
                    "type": "stemmer",
                    "language": "brazilian"
                },
                "code_strip": {
                    "type": "pattern_replace",
                    "pattern": "[\\s\\-/\\.]",
                    "replacement": ""
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "codprod":          {"type": "integer"},
            "descricao":        {"type": "text", "analyzer": "brazilian", "fields": {"raw": {"type": "keyword"}}},
            "marca":            {"type": "text", "analyzer": "brazilian", "fields": {"raw": {"type": "keyword"}}},
            "marca_codigo":     {"type": "integer"},
            "aplicacao":        {"type": "text", "analyzer": "brazilian"},
            "complemento":      {"type": "text", "analyzer": "brazilian"},
            "referencia":       {"type": "text", "analyzer": "code_analyzer", "fields": {"raw": {"type": "keyword"}}},
            "num_fabricante":   {"type": "text", "analyzer": "code_analyzer", "fields": {"raw": {"type": "keyword"}}},
            "num_fabricante2":  {"type": "text", "analyzer": "code_analyzer", "fields": {"raw": {"type": "keyword"}}},
            "num_original":     {"type": "text", "analyzer": "code_analyzer", "fields": {"raw": {"type": "keyword"}}},
            "ref_fornecedor":   {"type": "text", "analyzer": "code_analyzer", "fields": {"raw": {"type": "keyword"}}},
            "ncm":              {"type": "keyword"},
            "unidade":          {"type": "keyword"},
            "ativo":            {"type": "boolean"},
            "updated_at":       {"type": "date"},
            "all_codes":        {"type": "text", "analyzer": "code_analyzer"},
            "full_text":        {"type": "text", "analyzer": "brazilian"},
        }
    }
}

PARTNERS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "brazilian": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "brazilian_stem", "asciifolding"]
                }
            },
            "filter": {
                "brazilian_stem": {
                    "type": "stemmer",
                    "language": "brazilian"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "codparc":      {"type": "integer"},
            "nome":         {"type": "text", "analyzer": "brazilian", "fields": {"raw": {"type": "keyword"}}},
            "fantasia":     {"type": "text", "analyzer": "brazilian", "fields": {"raw": {"type": "keyword"}}},
            "cnpj_cpf":     {"type": "keyword"},
            "tipo":         {"type": "keyword"},
            "cidade":       {"type": "text", "analyzer": "brazilian", "fields": {"raw": {"type": "keyword"}}},
            "uf":           {"type": "keyword"},
            "bairro":       {"type": "text", "analyzer": "brazilian"},
            "telefone":     {"type": "keyword"},
            "email":        {"type": "keyword"},
            "vendedor":     {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "ativo":        {"type": "boolean"},
            "updated_at":   {"type": "date"},
            "full_text":    {"type": "text", "analyzer": "brazilian"},
        }
    }
}
