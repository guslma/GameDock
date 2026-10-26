<div align="center">
  <img src="app/static/logo/logo.svg" alt="GameDock" width="96" height="96">
  <h1>GameDock</h1>
  <p>A sua coleção de jogos de Nintendo Switch servida na sua rede, com a interface em português, inglês e espanhol.</p>
</div>

> **English:** GameDock is derived from [Ownfoil](https://github.com/a1ex4/ownfoil) and runs on its own, with a reorganized, easier interface in English, Portuguese and Spanish. Improvements from new Ownfoil releases can be brought in through pull requests, tested before they are merged. Use the image `ghcr.io/guslma/gamedock` in place of `a1ex4/ownfoil`, with the same `config` and `data` folders.

## O que é

O GameDock organiza os seus jogos de Nintendo Switch e os serve na rede para o Tinfoil, o Sphaira e outros clientes: biblioteca com capas, verificação dos arquivos, compressão, organização automática e estatísticas.

Ele nasceu do [Ownfoil](https://github.com/a1ex4/ownfoil), segue com código e imagem próprios e usa as mesmas pastas e configurações, então dá para trocar um pelo outro. O que muda:

- **Telas reorganizadas:** no menu, **Biblioteca**, **Conectar o console** e **Admin**. No Admin, só três itens:
  - **Visão geral:** os números da biblioteca, o que está rodando agora e os próximos agendamentos, **o que falta** (atualizações e DLC já lançadas que você ainda não tem), as tarefas que falharam e avisos do que precisa de atenção.
  - **Arquivos:** todos os arquivos, com filtros e ações (verificar, comprimir, identificar de novo, excluir).
  - **Configurações**, em abas: Biblioteca, Loja, Usuários, Avisos, Manutenção automática, Avançado e Logs, com um botão Salvar por aba e textos em linguagem simples. Em Logs dá para ver o registro do app, filtrar só avisos e erros, buscar e baixar.
- **Conectar o console:** os endereços de casa e de fora de casa com botão de copiar, e os passos do Sphaira, do Tinfoil e do CyberFoil lado a lado.
- **Avisos no celular** por ntfy, Telegram ou Discord: jogos, atualizações e DLC que entraram na biblioteca, atualização ou DLC nova disponível para um jogo seu, arquivo que falhou na verificação e tarefa que falhou.
- **Idiomas:** português, inglês e espanhol. Cada pessoa vê o idioma do próprio navegador e pode trocar pelo menu.
- **Biblioteca:** visualização em cartões, capas ou lista, e uma barra com busca, um menu de filtros (jogos ou DLC, o que tenho ou não, atualização, DLC) e um menu de exibição (itens por página e tamanho dos cartões).
- **Edição de usuários:** nome, senha e permissões, em **Admin → Configurações → Usuários**.
- **Melhorias do Ownfoil só se você quiser:** quando sai uma versão nova do Ownfoil, as mudanças dela chegam num pedido de atualização (pull request) com o resultado de um teste que abre todas as telas. Você aprova ou descarta; nada chega ao servidor sozinho.
- **Sobre:** clicar no logo mostra a versão do GameDock e o link do código-fonte dessa versão.

## Como instalar

Funciona em qualquer máquina Linux com Docker, como um mini PC, um NAS ou um Raspberry Pi.

```bash
sudo docker run -d --name gamedock \
  --network host \
  -e USER_ADMIN_NAME=admin \
  -e USER_ADMIN_PASSWORD=troque-esta-senha \
  -e TZ=America/Sao_Paulo \
  -v /caminho/dos/jogos:/games \
  -v ~/gamedock/config:/app/config \
  -v ~/gamedock/data:/app/data \
  --restart unless-stopped \
  ghcr.io/guslma/gamedock:latest
```

Depois, abra `http://IP-DA-MÁQUINA:8465` no navegador. A imagem funciona em computadores comuns (amd64) e em ARM de 64 bits (arm64, como Raspberry Pi 4 e 5 com sistema de 64 bits).

- `TZ` é o fuso horário, usado nos registros (**Admin → Configurações → Logs**) e nos agendamentos. Sem ele, o GameDock usa UTC. Em vez de escrever o fuso, dá para usar o da própria máquina com `-v /etc/localtime:/etc/localtime:ro`.
- O usuário de `USER_ADMIN_NAME` e `USER_ADMIN_PASSWORD` é recriado a cada início do contêiner. Para mudar a senha dele, mude a variável. Os outros usuários são criados e editados em **Admin → Configurações → Usuários**.
- A rede do host (`--network host`) faz o console achar o servidor sozinho (opção **Encontrar na rede de casa**) e deixa o GameDock ver o IP de verdade de cada console. Com ela, a porta é sempre a 8465.
- Onde a rede do host não funciona (Docker Desktop no Mac ou no Windows, por exemplo), troque `--network host` por `-p 8465:8465`, ou `network_mode: host` por `ports: ["8465:8465"]` no Compose. Tudo funciona igual, só que no console você digita o endereço em vez de procurar na rede.

Com Docker Compose:

```yaml
services:
  gamedock:
    image: ghcr.io/guslma/gamedock:latest
    container_name: gamedock
    # Rede do host: o console acha o servidor sozinho na rede de casa (porta 8465)
    network_mode: host
    environment:
      USER_ADMIN_NAME: admin
      USER_ADMIN_PASSWORD: troque-esta-senha
      # Fuso horário dos registros e agendamentos (lista: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
      TZ: America/Sao_Paulo
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

Depois, rode de novo o comando de instalação. Para fixar uma versão, use a tag dela, como `ghcr.io/guslma/gamedock:1.0.1`. As versões do GameDock estão no arquivo [`app/VERSION`](app/VERSION) e nas tags `vX.Y.Z` do repositório.

## Como funciona

- [`app/`](app) é o código do app, com versão própria em [`app/VERSION`](app/VERSION). Ele nasceu do código do Ownfoil e segue por conta própria; o arquivo [`UPSTREAM`](UPSTREAM) só registra até qual versão do Ownfoil as melhorias deles já foram trazidas, para a checagem diária saber o que é novo.
- A imagem é montada do zero a partir da imagem oficial do Python ([`Dockerfile`](Dockerfile)), com os pacotes de [`requirements.txt`](requirements.txt) nas versões fixas de [`requirements.lock`](requirements.lock). Não depende da imagem do Ownfoil.
- As telas são escritas em inglês. [`i18n/localize.py`](i18n/localize.py) gera uma cópia delas para cada idioma com os dicionários de [`locales/`](locales), e [`app/gamedock_i18n.py`](app/gamedock_i18n.py) escolhe o idioma de cada acesso. Um texto que o dicionário não conhece continua em inglês, sem quebrar nada.
- [`tests/smoke.sh`](tests/smoke.sh) sobe a imagem, entra e abre todas as telas nos 3 idiomas. Toda imagem passa por ele antes de ser publicada.
- [`.github/workflows/ownfoil.yaml`](.github/workflows/ownfoil.yaml) confere todo dia se saiu versão nova do Ownfoil e abre o pedido de atualização. Para ele conseguir abrir pull requests, ligue **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests** no repositório; sem isso, ele abre uma issue com o link das mudanças.

Os textos que ficaram sem tradução aparecem no resumo de cada execução em **Actions**.

### Adicionar um idioma

1. Copie `locales/es.json` para `locales/<código>.json` (por exemplo, `fr.json` ou `de.json`), troque `@name` pelo nome do idioma e traduza os valores. Os textos com `{{ }}` ou `{% %}` precisam manter esses trechos iguais, e as traduções não podem ter aspas.
2. Para ver todos os textos de uma tela, rode `python3 i18n/translate.py app textos.json`.
3. Envie o arquivo. A imagem nova já sai com o idioma no menu.

## Créditos e licença

O GameDock é uma versão modificada do [Ownfoil](https://github.com/a1ex4/ownfoil), de a1ex4 e colaboradores, e é distribuído sob a mesma licença, a [AGPL-3.0](LICENSE). O arquivo [`NOTICE`](NOTICE) lista o que foi modificado e os componentes de terceiros (Bootstrap, Bootstrap Icons e jQuery, sob licença MIT).

Pela AGPL, quem usa o GameDock pela rede tem direito ao código-fonte da versão que está rodando: o link **Código-fonte**, na janela **Sobre** (clicando no logo), aponta para ele. Quem publicar uma versão modificada precisa fazer o mesmo.

Nintendo Switch é marca da Nintendo. O GameDock não tem ligação com a Nintendo nem com o projeto Ownfoil.
