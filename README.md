# Dungeon Siege RPC

Projeto refatorado em módulos menores para facilitar manutenção e testes.

## Estrutura

- `dungeon_rpc/`: pacote principal
  - `main.py`: entry point CLI
  - `config.py`: constantes e configurações
  - `models.py`: tipos de dados
  - `regions.py`: mapeamento de regiões
  - `save_detector.py`: descoberta e monitoramento de saves
  - `save_monitor.py`: atualização do Discord RPC e loop do monitor
  - `parser/`: parsers do save
  - `integrations/`: integrações externas

## Execução

```bash
python -m dungeon_rpc.main --test-save caminho/para/save.dssave
```

Ou use o wrapper legado para manter compatibilidade com o nome antigo:

```bash
python dungeon.py
```
