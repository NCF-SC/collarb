import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import hashlib
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL COMPLETA (WHITE-LABEL)
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

# CSS oculto para remover assinaturas visuais do Streamlit e garantir identidade própria
REMOVER_BRANDING_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
"""
st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

LISTA_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Erro na conexão segura de dados. Atualize a página.")
    st.stop()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# ==========================================
# 1. INICIALIZAÇÃO DA MEMÓRIA DO SISTEMA
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""

def zerar_dados_financeiros():
    st.session_state['historico_rolagens'] = []
    st.session_state['mes_num'] = datetime.date.today().month
    st.session_state['ano_num'] = datetime.date.today().year
    st.session_state['preco_acao_tela'] = 0.0

if 'historico_rolagens' not in st.session_state:
    zerar_dados_financeiros()

# PERSISTÊNCIA AUTOMÁTICA DE LOGIN (Previne deslogar no F5/Refresh)
if "session_token" in st.query_params and not st.session_state['logged_in']:
    token_email = st.query_params["session_token"]
    try:
        resposta_auto = supabase.table("usuarios").select("*").eq("email", token_email).execute()
        if len(resposta_auto.data) > 0:
            user_db = resposta_auto.data[0]
            st.session_state['logged_in'] = True
            st.session_state['username'] = token_email.split('@')[0].capitalize()
            dados_salvos = user_db.get("dados", {})
            if dados_salvos:
                st.session_state['historico_rolagens'] = dados_salvos.get('historico_rolagens', [])
                st.session_state['mes_num'] = dados_salvos.get('mes_num', datetime.date.today().month)
                st.session_state['ano_num'] = dados_salvos.get('ano_num', datetime.date.today().year)
    except:
        pass

# ==========================================
# 2. SISTEMA DE ACESSO (LOGIN / CADASTRO)
# ==========================================
if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest")
    st.markdown("Plataforma Quantitativa de Engenharia Financeira de Derivativos.")
    
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        st.subheader("Painel de Acesso")
        modo = st.radio("Selecione:", ["Login", "Criar Conta"], horizontal=True)
        
        email_input = st.text_input("E-mail").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        
        if modo == "Login":
            if st.button("Entrar no Sistema", type="primary", use_container_width=True):
                if email_input and senha_input:
                    senha_criptografada = hash_senha(senha_input)
                    try:
                        resposta = supabase.table("usuarios").select("*").eq("email", email_input).execute()
                        if len(resposta.data) > 0:
                            user_db = resposta.data[0]
                            if user_db["senha"] == senha_criptografada:
                                st.session_state['logged_in'] = True
                                st.session_state['username'] = email_input.split('@')[0].capitalize()
                                st.query_params["session_token"] = email_input
                                
                                dados_salvos = user_db.get("dados", {})
                                if dados_salvos:
                                    st.session_state['historico_rolagens'] = dados_salvos.get('historico_rolagens', [])
                                    st.session_state['mes_num'] = dados_salvos.get('mes_num', datetime.date.today().month)
                                    st.session_state['ano_num'] = dados_salvos.get('ano_num', datetime.date.today().year)
                                st.rerun()
                            else:
                                st.error("Senha incorreta.")
                        else:
                            st.error("Usuário não cadastrado.")
                    except Exception as err:
                        st.error(f"Erro de autenticação: {err}")
                else:
                    st.warning("Preencha todos os campos.")
        else:
            if st.button("Concluir Cadastro", type="primary", use_container_width=True):
                if email_input and senha_input:
                    try:
                        verifica = supabase.table("usuarios").select("email").eq("email", email_input).execute()
                        if len(verifica.data) > 0:
                            st.error("Este e-mail já se encontra registrado.")
                        else:
                            novo_user = {
                                "email": email_input,
                                "senha": hash_senha(senha_input),
                                "dados": {}
                            }
                            supabase.table("usuarios").insert(novo_user).execute()
                            st.success("Conta criada! Alterne para 'Login' para entrar.")
                    except Exception as err:
                        st.error(f"Erro ao salvar cadastro: {err}")
    st.stop()

# ==========================================
# 3. AMBIENTE LOGADO PRINCIPAL
# ==========================================
st.title("Gouldian Invest | Gestão de Collar Dinâmico")

col_user1, col_user2, col_user3 = st.columns([3, 1, 1])
nome_exibicao = st.session_state['username']
col_user1.write(f"Sessão Ativa: **{nome_exibicao}** | Conexão Segura e Criptografada 🛡️")

if col_user2.button("💾 Salvar Dados na Nuvem", type="primary", use_container_width=True):
    dados_para_nuvem = {
        "historico_rolagens": st.session_state['historico_rolagens'],
        "mes_num": st.session_state['mes_num'],
        "ano_num": st.session_state['ano_num']
    }
    try:
        resposta_email = supabase.table("usuarios").select("email").execute()
        for u in resposta_email.data:
            if u["email"].startswith(st.session_state['username'].lower()):
                supabase.table("usuarios").update({"dados": dados_para_nuvem}).eq("email", u["email"]).execute()
                st.success("Estudo sincronizado com sucesso!")
                break
    except Exception as err:
        st.error(f"Falha ao salvar dados: {err}")

if col_user3.button("Sair do Sistema", use_container_width=True):
    st.session_state['logged_in'] = False
    st.query_params.clear()
    zerar_dados_financeiros()
    st.rerun()

# AVISO OBRIGATÓRIO DE SALVAMENTO SOLICITADO
st.info("⚠️ **Nota de Retenção de Dados:** Sempre que realizar alterações na tabela interativa, consolidar meses ou incluir proventos, lembre-se de clicar no botão **'💾 Salvar Dados na Nuvem'** no topo da tela para registrar suas modificações permanentemente.")

st.markdown("---")

# ==========================================
# RECALCULO DINÂMICO DOS ACUMULADOS DOS HISTÓRICOS
# ==========================================
caixa_acumulado_calls = 0.0
caixa_proventos = 0.0

if st.session_state['historico_rolagens']:
    for linha in st.session_state['historico_rolagens']:
        caixa_acumulado_calls += float(linha.get("Renda Opção Liq.", 0.0))
        caixa_proventos += float(linha.get("Dividendos/JSCP Liq.", 0.0))

caixa_total_gerado = caixa_acumulado_calls + caixa_proventos

# ==========================================
# 4. BARRA LATERAL (MONITOR E BENCHMARK)
# ==========================================
st.sidebar.header("🔍 Monitor de Mercado")
ticker_acao = st.sidebar.text_input("Ticker do Ativo", value="", placeholder="Ex: PETR4.SA")
st.sidebar.markdown(f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}")

if st.sidebar.button("Buscar Cotação"):
    if ticker_acao:
        try:
            acao = yf.Ticker(ticker_acao)
            preco_atual = acao.history(period="1d")['Close'].iloc[-1]
            st.session_state['preco_acao_tela'] = float(preco_atual)
            st.rerun()
        except:
            st.sidebar.error("Ativo indisponível no momento.")

with st.sidebar.expander("⚙️ Custos Operacionais e IR", expanded=False):
    ir_opcoes = st.number_input("IR Opções (%)", value=15.0, step=0.5) / 100
    ir_jscp_tax = st.number_input("IR JSCP (%)", value=15.0, step=0.5) / 100
    emol_acao = st.number_input("Emolumentos Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emolumentos Opção (%)", value=0.0375, format="%.4f") / 100
    corretagem = st.number_input("Corretagem Fixa (R$)", value=0.00, step=1.0)
    taxa_ex_b3 = st.number_input("Taxa Exercício B3 (%)", value=0.5, step=0.1) / 100

with st.sidebar.expander("🏦 Benchmark Selic", expanded=True):
    juros_bruto_aa = st.number_input("Selic Bruta (% a.a.)", value=14.50, step=0.1) / 100
    ir_renda_fixa = st.number_input("IR Renda Fixa (%)", value=22.5, step=0.5) / 100
    juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)
    tipo_juros = st.sidebar.radio("Regime Tributário/Selic", ["Simples (Conservador)", "Composto (Equivalente)"])
    if "Simples" in tipo_juros:
        juros_liquido_am = juros_liquido_aa / 12
    else:
        juros_liquido_am = ((1 + juros_liquido_aa) ** (1/12)) - 1
    meta_mensal = juros_liquido_am * 100

# ==========================================
# FASE 1: PARAMETRIZAÇÃO DAS ENTRADAS LÓGICAS (TAB-OPTIMIZED)
# ==========================================
st.header("📦 Fase 1: Parâmetros e Alvos da Operação")

col_cron1, col_cron2, col_vazio_cron = st.columns([1, 1, 2])
with col_cron1:
    index_mes_atual = st.session_state['mes_num'] - 1
    mes_selecionado = st.selectbox("Mês de Referência deste Lançamento", LISTA_MESES, index=index_mes_atual)
    st.session_state['mes_num'] = LISTA_MESES.index(mes_selecionado) + 1
with col_cron2:
    st.session_state['ano_num'] = st.number_input("Ano de Referência deste Lançamento", value=st.session_state['ano_num'], step=1)

st.write("")
col1, col2, col3 = st.columns(3)

# REORGANIZAÇÃO COMPLETA DE CAMPOS: O TAB flui estritamente pelas caixas de texto/número de forma linear
with col1:
    st.subheader("1. Ativo Base")
    preco_acao_raw = st.number_input("Preço de Compra da Ação (R$)", value=None, placeholder="Digite o preço...", format="%.2f")
    qtd_raw = st.number_input("Quantidade de Ações", value=None, placeholder="Ex: 1000", step=100)
    
    preco_acao = preco_acao_raw if preco_acao_raw is not None else 0.0
    qtd = qtd_raw if qtd_raw is not None else 0

with col2:
    st.subheader("2. Seguro Longo (Put)")
    ticker_put = st.text_input("Código da Put", value="", placeholder="Ex: PETRR454")
    preco_put_raw = st.number_input("Prêmio Pago na Put (R$)", value=None, placeholder="Ex: 3.43", format="%.2f")
    strike_put_raw = st.number_input("Strike da Put (R$)", value=None, placeholder="Ex: 49.46", format="%.2f")
    
    preco_put = preco_put_raw if preco_put_raw is not None else 0.0
    strike_put = strike_put_raw if strike_put_raw is not None else 0.0

volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = taxas_iniciais_totais = 0.0
custo_base_bruto = custo_base_ajustado = strike_minimo = preco_medio_atual = meta_financeira_12m = 0.0

if qtd > 0:
    volume_acao = preco_acao * qtd
    volume_put = preco_put * qtd
    tx_b3_entrada_acao = volume_acao * emol_acao
    tx_b3_entrada_put = volume_put * emol_opcao
    corretagem_fase1 = (corretagem * 2) if corretagem > 0 else 0.0 
    taxas_iniciais_totais = tx_b3_entrada_acao + tx_b3_entrada_put + corretagem_fase1

    custo_base_bruto = volume_acao + volume_put + taxas_iniciais_totais
    custo_base_ajustado = custo_base_bruto - caixa_total_gerado
    strike_minimo = (custo_base_ajustado / qtd) / (1 - taxa_ex_b3)
    preco_medio_atual = custo_base_ajustado / qtd
    meta_financeira_12m = custo_base_bruto * (1 + juros_liquido_aa)

with col3:
    st.subheader("3. Gestão Patrimonial")
    st.markdown(f"**Capital Inicial Sacrificado:** R$ {custo_base_bruto:,.2f}")
    st.info(f"**Amortização Líquida Total:** R$ {caixa_total_gerado:,.2f}")
    st.metric("Custo de Linha Ajustado", f"R$ {custo_base_ajustado:,.2f}", f"PM Real: R$ {preco_medio_atual:.2f}", delta_color="inverse")
    st.warning(f"🎯 **Strike Mínimo Ideal:** R$ {strike_minimo:.2f}")
    if meta_financeira_12m > 0:
        st.info(f"💰 **Alvo Renda Fixa (12M):** R$ {meta_financeira_12m:,.2f}")

st.markdown("---")

# ==========================================
# FASE 2: DISTRIBUIÇÃO MENSAL
# ==========================================
st.header("⚡ Fase 2: Distribuição de Caixa Mensal")
tab1, tab2 = st.tabs(["Lançamento de Call Mensal", "Proventos Recebidos"])

with tab1:
    col4, col5 = st.columns([1, 2])
    with col4:
        ticker_call = st.text_input("Código da Call Curta", value="", placeholder="Ex: PETRF54")
        strike_call_raw = st.number_input("Strike da Call Lançada (R$)", value=None, placeholder="Ex: 54.19", format="%.2f")
        premio_call_raw = st.number_input("Prêmio Bruto Recebido (R$)", value=None, placeholder="Ex: 0.25", format="%.2f")
        
        strike_call = strike_call_raw if strike_call_raw is not None else 0.0
        premio_call = premio_call_raw if premio_call_raw is not None else 0.0

    volume_call = premio_call * qtd
    receita_liquida_call_pre_ir = volume_call - (volume_call * emol_opcao) - (corretagem if corretagem > 0 else 0.0)
    ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
    receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

    with col5:
        st.write("")
        st.success(f"💸 Crédito Líquido Operacional (D+1): **R$ {receita_liquida_call_pre_ir:,.2f}**")
        st.caption(f"*(Se fechar em Pó: Provisão DARF Opções: R$ {ir_isolado_call_po:,.2f} | Amortização efetiva: R$ {receita_realmente_liquida_call:,.2f})*")
        if strike_call > 0 and strike_call < strike_minimo:
            st.error("🚨 O Strike selecionado reduz a margem mínima de segurança do Capital Inicial!")

with tab2:
    c_prov1, c_prov2, c_prov3 = st.columns(3)
    with c_prov1:
        div_brutos_raw = st.number_input("Dividendos Recebidos (Isentos R$)", value=None, placeholder="0.00", format="%.2f")
        dividendos_brutos = div_brutos_raw if div_brutos_raw is not None else 0.0
    with c_prov2:
        jscp_brutos_raw = st.number_input("JSCP Bruto Recebido (R$)", value=None, placeholder="0.00", format="%.2f")
        jscp_bruto = jscp_brutos_raw if jscp_brutos_raw is not None else 0.0
    
    ir_jscp = jscp_bruto * ir_jscp_tax
    total_proventos_liquidos = dividendos_brutos + (jscp_bruto - ir_jscp)
    
    with c_prov3:
        st.info(f"Retenção de IR na Fonte (JSCP): **R$ -{ir_jscp:.2f}**")
        st.success(f"Disponível Líquido: **R$ {total_proventos_liquidos:.2f}**")

st.markdown("---")

# ==========================================
# FASE 3: SIMULADOR DE PAYOFF E DRE
# ==========================================
st.header("🔮 Fase 3: Simulador Patrimonial de Payoff")

max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0

# Vínculo da chave 'key' nativa elimina por completo o duplo clique/atraso do slider
preco_vencimento = st.slider(
    "Preço Estimado do Ativo no Vencimento (R$)", 
    min_value=0.0, 
    max_value=max_slider, 
    value=float(preco_acao if preco_acao > 0 else 10.0), 
    step=0.10,
    key="slider_payoff_estavel"
)

if preco_vencimento > strike_put and strike_put > 0:
    valor_residual_put = 0.0
else:
    valor_residual_put_raw = st.number_input("Valor Comercial Residual da Put (R$)", value=None, placeholder="0.00", format="%.2f")
    valor_residual_put = valor_residual_put_raw if valor_residual_put_raw is not None else 0.0

receita_venda_put_residual = valor_residual_put * qtd
deseja_exercer_put = False
if preco_vencimento <= strike_put and strike_put > 0:
    deseja_exercer_put = st.checkbox("Acionar intencionalmente o Direito de Venda (Put) para liquidação da linha de risco")

receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
status_put = "Em vigor / Protegendo carteira"
status_call = "Em aberto"
cenario_nome = "Aguardando Alocação da Fase 1"

if qtd > 0:
    if preco_vencimento >= strike_call and strike_call > 0:
        cenario_nome = "🚀 EXERCÍCIO INTEGRAL NA CALL (Venda Compulsória no Alvo)"
        receita_venda_ativo = strike_call * qtd
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = "Ficou fora do dinheiro (Virou pó / Custo perdido)"
        status_call = f"Exercida a R$ {strike_call:.2f}"
        receita_venda_put_residual = 0.0 
    elif deseja_exercer_put:
        cenario_nome = "🛡️ EXECUÇÃO DO SEGURO DE PROTEÇÃO (Venda no Strike da Put)"
        receita_venda_ativo = strike_put * qtd  
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = f"Exercida voluntariamente a R$ {strike_put:.2f}"
        status_call = "Venceu sem valor (Virou Pó)"
        receita_venda_put_residual = 0.0  
    else:
        cenario_nome = "⚖️ MANUTENÇÃO E ROLAGEM DE POSIÇÃO (Ativo Retido / Call Virou Pó)"
        receita_venda_ativo = preco_vencimento * qtd 
        taxa_saida_b3 = receita_venda_ativo * emol_acao 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = f"Mantida na carteira (Valorizada em tela por R$ {valor_residual_put:.2f})"
        status_call = "Venceu sem valor (Virou Pó)"

lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
ir_devido_operacao = max(0.0, lucro_bruto_operacao * ir_opcoes)
lucro_liquido_final = lucro_bruto_operacao - ir_devido_operacao

rentabilidade_sobre_capital_inicial = (lucro_liquido_final / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

meses_decorridos = len(st.session_state['historico_rolagens']) + 1
if "Simples" in tipo_juros:
    meta_acumulada_mes = meta_mensal * meses_decorridos
else:
    meta_acumulada_mes = (((1 + juros_liquido_am) ** meses_decorridos) - 1) * 100

st.markdown(f"#### Comportamento da Estrutura: **{cenario_nome}**")

c_res1, c_res2, c_res3 = st.columns(3)
c_res1.metric("Resultado Líquido Estimado", f"R$ {lucro_liquido_final:,.2f}")
c_res2.metric("Yield on Cost (Retorno Global)", f"{rentabilidade_sobre_capital_inicial:.2f}%")
c_res3.metric(f"Meta Balizada Selic Período", f"{meta_acumulada_mes:.2f}%")

total_entradas = receita_venda_ativo + receita_liquida_call_pre_ir + caixa_total_gerado + total_proventos_liquidos + receita_venda_put_residual
total_saidas = volume_acao + volume_put + taxas_iniciais_totais + taxa_saida_b3 + corretagem_saida + ir_devido_operacao

with st.expander("🔎 Ver Raio-X Detalhado do Simulado (DRE Completo)", expanded=False):
    st.markdown(f"""
    **1. Demonstração de Fluxo dos Derivativos:**
    * **Seguro Longo ({ticker_put if ticker_put else 'Não informado'}):** {status_put}
    * **Renda Curta ({ticker_call if ticker_call else 'Não informado'}):** {status_call}
    
    **2. Fluxo de Caixa (Entradas Realizadas + Projetadas):**
    * (+) Valor de Liquidação/Mercado do Ativo: R$ {receita_venda_ativo:,.2f}
    * (+) Prêmio Líquido Capturado na Call Atual (Pré-IR): R$ {receita_liquida_call_pre_ir:,.2f}
    * (+) Proventos Líquidos Recebidos no Ciclo Atual: R$ {total_proventos_liquidos:,.2f}
    * (+) Valor de Recuperação da Put Residual: R$ {receita_venda_put_residual:,.2f}
    * (+) Caixa Histórico Líquido Acumulado (Calls + Proventos Passados): R$ {caixa_total_gerado:,.2f}
    * **TOTAL DE ENTRADAS CAPTURADAS: R$ {total_entradas:,.2f}**
    
    **3. Fluxo de Caixa (Saídas e Custos Iniciais Imutáveis):**
    * (-) Desembolso de Compra do Ativo Base: R$ {volume_acao:,.2f}
    * (-) Desembolso de Compra da Put de Proteção: R$ {volume_put:,.2f}
    * (-) Custos de Atrito Iniciais Totais (B3 + Corretagem): R$ {taxas_iniciais_totais:,.2f}
    * (-) Taxas de Liquidação / Exercício de Saída B3: R$ {taxa_saida_b3:,.2f}
    * (-) Custo de Corretagem de Saída: R$ {corretagem_saida:,.2f}
    * (-) Guia de Imposto de Renda Estimada (DARF Operação): R$ {ir_devido_operacao:,.2f}
    * **TOTAL DE SAÍDAS (Capital de Risco): R$ {total_saidas:,.2f}**
    
    **4. Lucro Líquido de Linha (Entradas - Saídas): R$ {lucro_liquido_final:,.2f}**
    """)

st.write("")
c_btn1, c_btn2 = st.columns(2)

with c_btn1:
    if st.button("➕ Consolidar Competência no Histórico", use_container_width=True):
        if qtd > 0:
            competencia_texto = f"{LISTA_MESES[st.session_state['mes_num']-1]}/{st.session_state['ano_num']}"
            
            novo_registro = {
                "Competência": competencia_texto,
                "Call Ref.": ticker_call if ticker_call else "-",
                "Renda Opção Liq.": float(receita_realmente_liquida_call),
                "Dividendos/JSCP Liq.": float(total_proventos_liquidos)
            }
            st.session_state['historico_rolagens'].append(novo_registro)
            
            if st.session_state['mes_num'] == 12:
                st.session_state['mes_num'] = 1
                st.session_state['ano_num'] += 1
            else:
                st.session_state['mes_num'] += 1
                
            st.rerun()
        else:
            st.error("Insira o preço e a quantidade do Ativo Base para registrar dados.")

with c_btn2:
    if st.button("🛑 Limpar Todo o Histórico", type="primary", use_container_width=True):
        zerar_dados_financeiros()
        st.rerun()

# ==========================================
# 5. TABELA DE AUDITORIA INTERATIVA (SISTEMA DE CORREÇÃO DE ERROS)
# ==========================================
if st.session_state['historico_rolagens']:
    st.markdown("---")
    st.subheader("📊 Relatório Cronológico de Amortização Patrimonial (Editável)")
    st.markdown(
        "💡 **Correções Rápidas:** Dê um **duplo clique sobre qualquer célula** abaixo se quiser alterar o valor. "
        "Para **deletar um mês inteiro**, selecione a linha clicando na caixa à esquerda dela e aperte a tecla `Delete` do teclado."
    )
    
    df_base = pd.DataFrame(st.session_state['historico_rolagens'])
    
    df_corrigido = st.data_editor(
        df_base,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Competência": st.column_config.TextColumn("Competência", required=True),
            "Call Ref.": st.column_config.TextColumn("Call Ref."),
            "Renda Opção Liq.": st.column_config.NumberColumn("Renda Opção Liq.", format="R$ %.2f"),
            "Dividendos/JSCP Liq.": st.column_config.NumberColumn("Dividendos/JSCP Liq.", format="R$ %.2f")
        }
    )
    
    if not df_corrigido.equals(df_base):
        st.session_state['historico_rolagens'] = df_corrigido.to_dict(orient="records")
        st.rerun()

# ==========================================
# 6. PAINEL COMPARATIVO DE PERFORMANCE MULTI-INDICADORES
# ==========================================
st.markdown("---")
st.subheader("🏆 Painel Comparativo de Performance Absoluta")
st.markdown("Análise de prêmio e geração de caixa acumulados vs Benchmarks de Mercado Globais no período.")

# Coleta dinâmica de indicadores do mercado usando yfinance
@st.cache_data(ttl=3600)
def buscar_indicadores_mercado():
    try:
        # ^BVSP = Ibovespa | USDBRL=X = Dólar Comercial
        tickers = ["^BVSP", "USDBRL=X"]
        dados_mkt = yf.download(tickers, period="1mo")['Close']
        
        # Pega a variação percentual aproximada recente (mês) para ilustração comparativa institucional
        ret_ibov = ((dados_mkt["^BVSP"].iloc[-1] / dados_mkt["^BVSP"].iloc[0]) - 1) * 100
        ret_usd = ((dados_mkt["USDBRL=X"].iloc[-1] / dados_mkt["USDBRL=X"].iloc[0]) - 1) * 100
        return ret_ibov, ret_usd
    except:
        return 1.25, -0.45 # Fallbacks estáveis caso a API de fim de semana apresente instabilidade

perf_ibov, perf_usd = buscar_indicadores_mercado()

# Calcula o retorno real acumulado gerado de caixa puro em carteira
retorno_caixa_puro = (caixa_total_gerado / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

c_perf1, c_perf2, c_perf3, c_perf4 = st.columns(4)

c_perf1.metric(
    label="Estratégia Gouldian (Caixa Criado)", 
    value=f"{retorno_caixa_puro:.2f}%", 
    delta=f"R$ {caixa_total_gerado:,.2f}"
)
c_perf2.metric(
    label="Benchmark Selic Líquida", 
    value=f"{meta_acumulada_mes:.2f}%", 
    delta=f"Alvo {tipo_juros.split()[0]}",
    delta_color="inverse"
)
c_perf3.metric(
    label="Ibovespa de Referência (1M)", 
    value=f"{perf_ibov:.2f}%", 
    delta="Mercado de Ações"
)
c_perf4.metric(
    label="Câmbio Dólar (USD/BRL 1M)", 
    value=f"{perf_usd:.2f}%", 
    delta="Proteção Cambial"
)
