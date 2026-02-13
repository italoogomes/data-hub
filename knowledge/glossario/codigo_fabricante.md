# Codigo do Fabricante

**O que e:** Codigo alfanumerico atribuido pelo fabricante para identificar uma peca. Cada fabricante tem sua propria codificacao. Ex: HU711/51 (MANN), WK 950/21 (MANN), P550162 (DONALDSON).

**No sistema:** Armazenado em multiplos campos de TGFPRO:
- `REFERENCIA` - referencia principal do fabricante
- `AD_NUMFABRICANTE` - numero do fabricante (campo customizado)
- `AD_NUMFABRICANTE2` - segundo numero do fabricante
- `AD_NUMORIGINAL` - numero original da peca (OEM)
- `REFFORN` - referencia do fornecedor

**Tabelas relacionadas:** TGFPRO (campos acima), AD_TGFPROAUXMMA (codigos auxiliares/cross-reference)

**Termos equivalentes:** referencia, numero fabricante, codigo fabricante, numero original, ref, refforn

**Busca no agente:** O Smart Agent normaliza codigos removendo espacos, tracos e barras antes de comparar. Assim "HU711/51", "HU71151", "HU 711/51" encontram o mesmo produto.

**Exemplo pratico:**
- Usuario digita "HU711/51"
- Sistema busca em TGFPRO nos 5 campos de referencia
- Se nao encontra, busca em AD_TGFPROAUXMMA (auxiliares)
- Retorna produto(s) encontrado(s) com o campo que matchou
