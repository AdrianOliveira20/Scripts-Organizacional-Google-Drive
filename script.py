"""
Script para renomear arquivos de leis no Google Drive.

Pré-requisitos:
1. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
2. Criar projeto no Google Cloud Console, ativar Drive API e baixar credentials.json
   https://console.cloud.google.com/
3. Colocar o arquivo credentials.json na mesma pasta deste script

Uso:
- Defina FOLDER_ID abaixo com o ID da pasta no Drive (veja URL da pasta).
- Execute: python script.py
"""

import re
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cole aqui o ID da pasta no Google Drive.
# Para encontrar: abra a pasta no Drive, o ID está na URL após /folders/
# Ex: https://drive.google.com/drive/folders/1ABC123XYZ  →  FOLDER_ID = "1ABC123XYZ"
FOLDER_ID = "162FH1DBUCaplAf1bvcLKryfOg35brlt-"


def autenticar():
    creds = None
    token_path = os.path.join(BASE_DIR, "token.json")
    credentials_path = os.path.join(BASE_DIR, "credentials.json")
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def extrair_numero_e_ano(nome_arquivo):
    """
    Tenta extrair número e ano de lei a partir do nome do arquivo.
    Retorna (numero, ano) como strings, ou (None, None) se não encontrado.
    """
    nome = nome_arquivo

    # Remove extensão para facilitar (apenas extensões reais: curtas e sem espaço)
    nome_sem_ext = re.sub(r'\.[a-zA-Z0-9]{1,5}$', '', nome)

    # Padrões em ordem de especificidade
    padroes = [
        # "Lei n 1234 - 2021" (formato final já correto)
        r'[Ll]ei\s+n\s+(\d+)\s+-\s+(\d{4})',
        # "Lei nº 1234/2021" ou "Lei n 1234/2021"
        r'[Ll]ei\s+n[º°\.]?\s*(\d+)\s*/\s*(\d{2,4})',
        # "Lei n.º 1234 de 2021" (qualquer variante de º, espaços extras)
        r'[Ll]ei\s+n[^0-9\s]*\s*(\d+)\s+de\s+(\d{2,4})',
        # "Lei número/numero 1234 do ano de 2021"
        r'[Ll]ei\s+n[úu]mero\s+(\d+)\s+do\s+ano\s+de\s+(\d{2,4})',
        # "Lei número/numero 1234 de 2021"
        r'[Ll]ei\s+n[úu]mero\s+(\d+)\s+de\s+(\d{2,4})',
        # "Lei número/numero 1234 2021"
        r'[Ll]ei\s+n[úu]mero\s+(\d+)\s+(\d{4})',
        # "Lei n.º 1234 de 2021"
        r'[Ll]ei\s+n\.\s*[º°]?\s*(\d+)\s+de\s+(\d{2,4})',
        # "Lei 1234 de 2021" ou "Lei_1234_de_2021"
        r'[Ll]ei[\s_]+(\d+)[\s_]+de[\s_]+(\d{2,4})',
        # "Lei 1234 2021" ou "Lei_1234_2021"
        r'[Ll]ei[\s_]+(\d+)[\s_]+(\d{4})',
        # Apenas "1234-2021" ou "1234_2021" ou "1234 2021"
        r'(\d+)[-_\s](\d{4})',
    ]

    for padrao in padroes:
        match = re.search(padrao, nome_sem_ext)
        if match:
            numero = match.group(1).lstrip("0") or "0"
            ano = match.group(2)
            # Converte ano de 2 dígitos para 4
            if len(ano) == 2:
                ano = ("20" if int(ano) <= 30 else "19") + ano
            return numero, ano

    return None, None


def listar_arquivos(service, folder_id):
    arquivos = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
        ).execute()
        arquivos.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return arquivos


def renomear_arquivo(service, file_id, novo_nome):
    service.files().update(fileId=file_id, body={"name": novo_nome}).execute()


def main():
    creds = autenticar()
    service = build("drive", "v3", credentials=creds)

    print(f"Buscando arquivos na pasta {FOLDER_ID}...\n")
    arquivos = listar_arquivos(service, FOLDER_ID)

    if not arquivos:
        print("Nenhum arquivo encontrado na pasta.")
        return

    renomeados = 0
    nao_reconhecidos = []

    for arquivo in arquivos:
        nome_original = arquivo["name"]
        file_id = arquivo["id"]

        # Preserva extensão (apenas extensões reais: curtas e sem espaço)
        match_ext = re.search(r'(\.[a-zA-Z0-9]{1,5})$', nome_original)
        extensao = match_ext.group(1) if match_ext else ""

        numero, ano = extrair_numero_e_ano(nome_original)

        if numero and ano:
            novo_nome = f"Lei n {numero} - {ano}{extensao}"
            if novo_nome == nome_original:
                print(f"[=] Já correto: {nome_original}")
                continue
            print(f"[OK] {nome_original}  ->  {novo_nome}")
            renomear_arquivo(service, file_id, novo_nome)
            renomeados += 1
        else:
            print(f"[?] Não reconhecido: {nome_original}")
            nao_reconhecidos.append(nome_original)

    print(f"\nConcluído. {renomeados} arquivo(s) renomeado(s).")
    if nao_reconhecidos:
        print(f"\nArquivos não reconhecidos ({len(nao_reconhecidos)}):")
        for n in nao_reconhecidos:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
