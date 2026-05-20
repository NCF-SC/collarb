# ======================================================
# MOTOR BRAPI V2 OFICIAL PARA OPÇÕES B3
# ======================================================

def buscar_dados_opcao_brapi(ticker_opcao):

    if not ticker_opcao:
        return None

    token = st.secrets.get("BRAPI_TOKEN", "")

    if not token:
        st.error("BRAPI_TOKEN não encontrado no secrets.toml")
        return None

    ticker_opcao = ticker_opcao.upper().strip()

    # =====================================
    # DESCOBRE ATIVO BASE
    # =====================================

    base4 = ticker_opcao[:4]

    mapa_ativos = {
        "PETR": "PETR4",
        "VALE": "VALE3",
        "ITUB": "ITUB4",
        "BBDC": "BBDC4",
        "BBAS": "BBAS3",
        "ABEV": "ABEV3",
        "WEGE": "WEGE3",
        "MGLU": "MGLU3",
        "JBSS": "JBSS3",
        "PRIO": "PRIO3",
        "SUZB": "SUZB3",
        "RENT": "RENT3",
        "LREN": "LREN3",
        "EQTL": "EQTL3",
        "BPAC": "BPAC11"
    }

    underlying = mapa_ativos.get(base4)

    if not underlying:
        st.error(f"Não consegui identificar o ativo base de {ticker_opcao}")
        return None

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:

        # =====================================
        # 1. BUSCA VENCIMENTOS
        # =====================================

        url_exp = "https://brapi.dev/api/v2/options/expirations"

        r_exp = requests.get(
            url_exp,
            params={
                "underlying": underlying
            },
            headers=headers,
            timeout=15
        )

        if r_exp.status_code == 401:
            st.error("Token BRAPI inválido.")
            return None

        if r_exp.status_code != 200:
            st.error(f"Erro ao consultar vencimentos: {r_exp.status_code}")
            return None

        expirations_data = r_exp.json()

        expirations = expirations_data.get("expirations", [])

        if not expirations:
            st.warning("Nenhum vencimento encontrado.")
            return None

        # =====================================
        # 2. PROCURA A OPÇÃO EM TODOS VENCIMENTOS
        # =====================================

        for vencimento in expirations:

            url_chain = "https://brapi.dev/api/v2/options/chain"

            r_chain = requests.get(
                url_chain,
                params={
                    "underlying": underlying,
                    "expirationDate": vencimento
                },
                headers=headers,
                timeout=15
            )

            if r_chain.status_code != 200:
                continue

            chain_data = r_chain.json()

            series = chain_data.get("series", [])

            for opcao in series:

                symbol = opcao.get("symbol", "").upper()

                if symbol == ticker_opcao:

                    strike = opcao.get("strike", 0.0)
                    close = opcao.get("close", 0.0)
                    side = opcao.get("side", "")
                    volume = opcao.get("volume", 0)

                    vencimento_date = datetime.datetime.strptime(
                        vencimento,
                        "%Y-%m-%d"
                    ).date()

                    return {
                        "preco": float(close) if close else 0.0,
                        "strike": float(strike) if strike else 0.0,
                        "vencimento": vencimento_date,
                        "tipo": side,
                        "volume": volume,
                        "underlying": underlying
                    }

        st.warning(f"Opção {ticker_opcao} não encontrada na cadeia da B3.")
        return None

    except requests.exceptions.Timeout:
        st.error("Timeout na comunicação com a BRAPI.")
        return None

    except requests.exceptions.ConnectionError:
        st.error("Falha de conexão com a internet ou BRAPI.")
        return None

    except Exception as e:
        st.error(f"Erro BrAPI: {e}")
        return None
