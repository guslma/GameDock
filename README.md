<div align="center">
  <img src="app/static/logo/logo.svg" alt="GameDock" width="96" height="96">
  <h1>GameDock</h1>
  <p>A sua coleção de jogos de Nintendo Switch servida na sua rede, com a interface em português, inglês e espanhol.</p>
</div>

> **English:** GameDock is based on [Ownfoil](https://github.com/a1ex4/ownfoil), with a reorganized, easier interface in English, Portuguese and Spanish. New Ownfoil releases arrive as pull requests, tested before they are merged. Use the image `ghcr.io/guslma/gamedock` in place of `a1ex4/ownfoil`, with the same `config` and `data` folders.

## O que é

O GameDock organiza os seus jogos de Nintendo Switch e os serve na rede para o Tinfoil, o Sphaira e outros clientes: biblioteca com capas, verificação dos arquivos, compressão, organização automática e estatísticas.

Ele é baseado no [Ownfoil](https://github.com/a1ex4/ownfoil) e usa as mesmas pastas e configurações. O que muda:

- **Telas reorganizadas:** no menu, **Biblioteca**, **Conectar o console** e **Admin**. No Admin, só três itens:
  - **Visão geral:** os números da biblioteca, o que está rodando agora, os próximos agendamentos e avisos do que precisa de atenção.
  - **Arquivos:** todos os arquivos, com filtros e ações (verificar, comprimir, identificar de novo, excluir).
  - **Configurações**, em abas: Loja, Biblioteca, Usuários, Manutenção automática e Avançado, com um botão Salvar por aba e textos em linguagem simples.
- **Conectar o console:** os endereços de casa e de fora de casa com botão de copiar, e os passos do Sphaira, do Tinfoil e do CyberFoil lado a lado.
- **Idiomas:** português, inglês e espanhol. Cada pessoa vê o idioma do próprio navegador e pode trocar pelo menu.
- **Biblioteca em lista**, além dos cartões e das capas, e filtros visíveis (jogos ou DLC, o que tenho ou não, atualização, DLC).
- **Edição de usuários:** nome, senha e permissões.
- **Atualizações do Ownfoil com segurança:** quando sai uma versão nova, um pedido de atualização (pull request) é aberto sozinho com as mudanças e o resultado de um teste que abre todas as telas. Nada chega ao servidor sem aprovação.

## Como instalar

Funciona em qualquer máquina Linux com Docker, como um mini PC, um NAS ou um Raspberry Pi.

```bash
sudo docker run -d --name gamedock \
  -p 8465:8465 \
  -e USER_ADMIN_NAME=admin \
  -e USER_ADMIN_PASSWORD=troque-esta-senha \
  -v /caminho/dos/jogos:/games \
  -v ~/gamedock/config:/app/config \
  -v ~/gamedock/data:/app/data \
  --restart unless-stopped \
  ghcr.io/guslma/gamedock:latest
```

Depois, abra `http://IP-DA-MÁQUINA:8465` no navegador. A imagem funciona em computadores comuns (amd64) e em ARM (arm64 e armv7).

Com Docker Compose:

```yaml
services:
  gamedock:
    image: ghcr.io/guslma/gamedock:latest
    container_name: gamedock
    ports:
      - 8465:8465
    environment:
      USER_ADMIN_NAME: admin
      USER_ADMIN_PASSWORD: troque-esta-senha
      # Idioma para quem não escolheu nenhum e usa um navegador num idioma sem tradução
      GAMEDOCK_LANGUAGE: pt-BR
    volumes:
      - /caminho/dos/jogos:/games
      - ./config:/app/config
      - ./data:/app/data
    restart: unless-stopped
```

### Vindo do Ownfoil

Troque a imagem `a1ex4/ownfoil` por `ghcr.io/guslma/gamedock` e mantenha as mesmas pastas `config` e `data`: a biblioteca, os usuários e as configurações continuam como estavam. Se o nome da loja estiver como "Ownfoil", mude em **Admin → Configurações → Loja**.

No Sphaira, o menu continua se chamando **Ownfoil**, porque esse é o nome que o próprio Sphaira mostra.

### Atualizar

```bash
sudo docker pull ghcr.io/guslma/gamedock:latest
sudo docker rm -f gamedock
```

Depois, rode de novo o comando de instalação. Para fixar uma versão, use a tag dela, como `ghcr.io/guslma/gamedock:1.0.0`.

## Como funciona

- [`app/`](app) é o código do app. Começou do Ownfoil 2.5.0 (o arquivo [`UPSTREAM`](UPSTREAM) diz qual versão) e tem as telas e recursos do GameDock.
- A imagem usa a oficial do Ownfoil da mesma versão só como base, pelo Python e pelas ferramentas que ela já traz, e troca o código do app pelo do GameDock ([`Dockerfile`](Dockerfile)).
- As telas são escritas em inglês. [`i18n/localize.py`](i18n/localize.py) gera uma cópia delas para cada idioma com os dicionários de [`locales/`](locales), e [`app/gamedock_i18n.py`](app/gamedock_i18n.py) escolhe o idioma de cada acesso. Um texto que o dicionário não conhece continua em inglês, sem quebrar nada.
- [`tests/smoke.sh`](tests/smoke.sh) sobe a imagem, entra e abre todas as telas nos 3 idiomas. Toda imagem passa por ele antes de ser publicada.
- [`.github/workflows/ownfoil.yaml`](.github/workflows/ownfoil.yaml) confere todo dia se saiu versão nova do Ownfoil e abre o pedido de atualização.

Os textos que ficaram sem tradução aparecem no resumo de cada execução em **Actions**.

### Adicionar um idioma

1. Copie `locales/es.json` para `locales/<código>.json` (por exemplo, `fr.json` ou `de.json`), troque `@name` pelo nome do idioma e traduza os valores. Os textos com `{{ }}` ou `{% %}` precisam manter esses trechos iguais, e as traduções não podem ter aspas.
2. Para ver todos os textos de uma tela, rode `python3 i18n/translate.py app textos.json`.
3. Envie o arquivo. A imagem nova já sai com o idioma no menu.

## Créditos e licença

O GameDock é baseado no [Ownfoil](https://github.com/a1ex4/ownfoil), de a1ex4, e distribuído sob a mesma licença, a AGPL-3.0. Veja o arquivo [`LICENSE`](LICENSE).
