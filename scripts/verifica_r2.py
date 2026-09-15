#!/usr/bin/env python3
"""Controlla che le credenziali R2 funzionino davvero, prima di fidarsene.

Che i quattro secret esistano su GitHub non dimostra niente: i nomi si vedono,
i valori no. Questo script fa il giro completo — scrive un oggetto di prova, lo
rilegge, lo elenca, lo cancella — e dice a quale passo si rompe. Serve oggi per
il collaudo e servira' il giorno in cui il caricamento notturno fallira' e
bisognera' capire se e' colpa delle chiavi, del permesso o del secchio.

    python scripts/verifica_r2.py

Le chiavi arrivano dall'ambiente e non vengono mai stampate: di ognuna si
mostra solo la lunghezza e le ultime quattro lettere, che bastano a capire se
si e' incollato il valore sbagliato senza metterlo negli archivi pubblici di
GitHub Actions.
"""
from __future__ import annotations

import os
import sys
import datetime as dt

ATTESI = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET')


def impronta(nome: str, valore: str) -> str:
    """Quanto basta per riconoscere un valore senza rivelarlo."""
    return f'{nome}: {len(valore)} caratteri, finisce con ...{valore[-4:]}'


def leggi_ambiente() -> dict | None:
    """Le quattro variabili, con i controlli che evitano le sere perse."""
    mancanti = [k for k in ATTESI if not os.environ.get(k)]
    if mancanti:
        print('MANCANO:', ', '.join(mancanti))
        print('Sono i secret del repository, in Settings → Secrets and variables → Actions.')
        return None

    valori, sporchi = {}, []
    for k in ATTESI:
        grezzo = os.environ[k]
        pulito = grezzo.strip()
        if pulito != grezzo:
            # Copiando dalla schermata di Cloudflare ci si porta dietro uno
            # spazio o un a capo: la firma S3 non torna e l'errore non lo dice.
            sporchi.append(k)
        valori[k] = pulito

    for k in ATTESI:
        print('  ' + impronta(k, valori[k]))
    if sporchi:
        print(f'\nATTENZIONE: {", ".join(sporchi)} conteneva spazi o a capo ai bordi.')
        print('Qui li tolgo, ma conviene reincollare il secret pulito.')
    return valori


def main() -> int:
    print('— credenziali —')
    v = leggi_ambiente()
    if not v:
        return 1

    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError
    except ImportError:
        print('\nserve boto3:  pip install boto3')
        return 1

    endpoint = f"https://{v['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    secchio = v['R2_BUCKET']
    print(f'\n— destinazione —\n  {endpoint}\n  secchio: {secchio}')

    s3 = boto3.client(
        's3', endpoint_url=endpoint,
        aws_access_key_id=v['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=v['R2_SECRET_ACCESS_KEY'],
        # R2 non ha regioni: 'auto' e' il valore che si aspetta.
        region_name='auto',
        config=Config(signature_version='s3v4', retries={'max_attempts': 2}))

    chiave = f"_verifica/{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}.txt"
    corpo = b'efficiency-life: prova di scrittura, si puo cancellare'
    print(f'\n— giro di prova —\n  oggetto: {chiave}')

    def passo(etichetta, funzione, indispensabile=True):
        try:
            funzione()
            print(f'  OK        {etichetta}')
            return True
        except ClientError as e:
            codice = e.response.get('Error', {}).get('Code', '?')
            print(f'  {"FALLITO " if indispensabile else "non fatto"}  {etichetta} — {codice}')
            if indispensabile:
                print(f'\n{SPIEGAZIONI.get(codice, "Errore completo: " + str(e))}')
            return False
        except Exception as e:  # rete, DNS, TLS
            print(f'  FALLITO   {etichetta} — {type(e).__name__}: {e}')
            return False

    if not passo('scrittura  (PutObject)',
                 lambda: s3.put_object(Bucket=secchio, Key=chiave, Body=corpo)):
        return 1

    letto = {}
    if not passo('rilettura  (GetObject)',
                 lambda: letto.update(
                     dati=s3.get_object(Bucket=secchio, Key=chiave)['Body'].read())):
        return 1
    if letto.get('dati') != corpo:
        print('\nFALLITO: l\'oggetto riletto non e\' identico a quello scritto.')
        return 1
    print('         contenuto identico a quello scritto')

    passo('elenco     (ListObjectsV2)',
          lambda: s3.list_objects_v2(Bucket=secchio, Prefix='_verifica/', MaxKeys=5))

    # La cancellazione non e' indispensabile: l'archivio non cancella mai
    # niente, e un token che sa solo scrivere va benissimo lo stesso.
    pulito = passo('cancellazione (DeleteObject)',
                   lambda: s3.delete_object(Bucket=secchio, Key=chiave),
                   indispensabile=False)

    print('\n— esito —')
    print('  Le credenziali funzionano: si puo scrivere e rileggere.')
    if not pulito:
        print(f'  L\'oggetto di prova e\' rimasto: {chiave}. Innocuo, pesa 53 byte.')
    return 0


SPIEGAZIONI = {
    'InvalidAccessKeyId':
        'La Access Key ID non esiste. Hai incollato il valore sbagliato, oppure\n'
        'il token e\' stato revocato: rifallo in R2 → Manage API tokens.',
    'SignatureDoesNotMatch':
        'La Secret Access Key non corrisponde. Quasi sempre e\' un carattere di\n'
        'troppo incollato per sbaglio: rigenera il token e reincolla il secret.',
    'AccessDenied':
        'Chiavi valide ma permesso insufficiente. Il token deve avere\n'
        '"Object Read & Write" e includere questo secchio fra quelli consentiti.\n'
        'Se hai messo un filtro per indirizzo IP, toglilo: i runner di GitHub\n'
        'cambiano indirizzo a ogni esecuzione.',
    'NoSuchBucket':
        'Il secchio non esiste con questo nome. Controlla R2_BUCKET: deve essere\n'
        'esattamente il nome che si legge nella dashboard, minuscole comprese.',
}


if __name__ == '__main__':
    raise SystemExit(main())
