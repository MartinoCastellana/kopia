# Kopia

Gestore desktop macOS per automatizzare trasferimenti FTP/FTPS, conservare gli originali, generare derivati PDF/TIFF e creare backup verificati.

**Versione corrente: `0.0.1`**

> Progetto in sviluppo. Prima di usarlo su dati reali, esegui un test con un server FTP dedicato e lascia disattivata la cancellazione remota.

## Funzionalità

- Connessioni FTP e FTPS con verifica TLS.
- Download ricorsivo con conservazione della struttura remota.
- Storage cumulativo degli originali e versionamento dei file modificati.
- Conversione PDF in TIFF multipagina CCITT Group 4 a 600 DPI.
- Generazione di PDF compressi a 300 DPI senza encoder esterni.
- Backup daily e weekly in ZIP con manifesto SHA256.
- Copia secondaria opzionale con verifica dell’integrità.
- Retention configurabile per progetto.
- Report JSON e log dettagliati per ogni ciclo.
- Automazioni native macOS tramite `launchd`.
- Interfaccia Tk macOS con panoramica, progetti, automazioni e guida.

## Requisiti

- macOS 12 o successivo.
- Python 3.11 o successivo.
- Accesso a un server FTP/FTPS.

## Caso studio di riferimento

Lo scenario di riferimento è composto da:

| Componente | Specifiche |
|---|---|
| Server remoto | Server Linux con AlmaLinux, raggiungibile tramite FTP/FTPS |
| Client Kopia | MacBook Pro con Apple M1 Pro |
| CPU | 8 core: 6 performance + 2 efficiency |
| Memoria | 16 GB RAM |
| Sistema operativo | macOS 15.7.4, build 24G517 |
| Architettura | Apple Silicon arm64 |
| Spazio locale rilevato | Volume principale da circa 460 GB, con circa 54 GB disponibili |

Il server AlmaLinux rappresenta la sorgente remota dei documenti. Kopia viene eseguito sul Mac e mantiene localmente lo storage cumulativo, i TIFF derivati, i backup e i log. Il server remoto non viene usato come destinazione dei backup locali: viene modificato solo il PDF remoto quando il ciclo produce una versione compressa verificata.

### Flusso del caso studio

```text
Server AlmaLinux
        │
        │ FTP / FTPS
        ▼
MacBook Pro · Apple M1 Pro · 16 GB
        │
        ├── Storage cumulativo / originals
        ├── Derivati TIFF / tiff
        ├── Versioni precedenti / versions
        ├── Backup daily
        ├── Backup weekly
        └── Log, stato e report JSON
```

La connessione consigliata è FTPS con verifica del certificato TLS e modalità passiva. Le cartelle locali di storage, backup daily, backup weekly e log devono essere separate. La copia secondaria può essere collocata su un secondo volume macOS o su un disco esterno montato stabilmente.

Questo caso studio è adatto a documenti PDF e file di dimensione medio-alta. La conversione TIFF a 600 DPI può richiedere memoria significativa con PDF multipagina molto grandi; sul Mac di riferimento i 16 GB RAM sono sufficienti per cicli ordinari, mentre per archivi voluminosi è consigliato dividere i progetti o pianificare i cicli fuori dall’orario di lavoro.

## Installazione

```zsh
git clone <URL_DEL_REPOSITORY>
cd Kopia
./install_mac.sh
```

Lo script crea l’ambiente virtuale e installa le dipendenze applicative e di build.

## Avvio

```zsh
./start_mac.command
```

Al primo avvio crea un progetto, configura la connessione e usa **Verifica connessione** prima di eseguire un ciclo.

## Build dell’app macOS

```zsh
./build_mac.sh
open dist/Kopia.app
```

La build esegue prima tutti i test e poi produce l’app standalone in `dist/`.

## Automazioni

Dalla sezione **Automazioni** puoi installare o aggiornare i cicli daily e weekly. L’app crea agenti per l’utente corrente in:

```text
~/Library/LaunchAgents/
```

Gli orari vengono letti dalla configurazione del progetto. Per rimuovere le automazioni, disattiva i cicli e reinstalla la configurazione oppure elimina il progetto.

## Dati applicativi

Per impostazione predefinita i dati vengono salvati in:

```text
~/Library/Application Support/Kopia
```

È possibile impostare una directory alternativa:

```zsh
export KOPIA_DATA="$HOME/Documents/Kopia-data"
./start_mac.command
```

La cartella contiene configurazione, log, lock, stato dei file e report dei cicli. Le password sono archiviate nella configurazione locale: proteggi l’accesso al computer e alla directory dati.

## Backup frammentati e verificati

Kopia mantiene due catene di backup indipendenti: **daily** e **weekly**. La separazione evita che la retention dei backup frequenti elimini i punti di ripristino settimanali e permette di usare destinazioni diverse, anche su volumi differenti.

### Backup daily

Il ciclo daily:

1. scansiona la cartella remota;
2. scarica i file nello storage cumulativo `originals/`;
3. conserva le versioni precedenti in `versions/` quando un file cambia;
4. genera i TIFF in `tiff/` per i PDF;
5. aggiorna la catena incrementale nella directory **Backup daily**.

### Backup weekly

Il ciclo weekly non richiede un nuovo download FTP: fotografa lo storage cumulativo già verificato e aggiorna una catena incrementale separata nella directory **Backup weekly**. In questo modo il weekly conserva lo stato locale completo, inclusi originali, TIFF e versioni.

### Impostazioni disponibili

Ogni progetto può configurare:

- **Storage cumulativo**: destinazione degli originali, dei TIFF e delle versioni.
- **Backup daily**: directory della catena giornaliera.
- **Backup weekly**: directory della catena settimanale, obbligatoriamente diversa dal daily.
- **Retention daily**: quantità configurata di archivi daily completi da conservare.
- **Retention weekly**: quantità configurata di archivi weekly completi da conservare.
- **Copia secondaria**: attivabile separatamente, con directory di destinazione dedicata.
- **Orario daily**: ora e minuto dell’automazione giornaliera.
- **Orario weekly**: giorno della settimana, ora e minuto dell’automazione settimanale.
- **Backup e log separati**: Kopia impedisce cartelle uguali o annidate per evitare contaminazioni e cancellazioni accidentali.

Gli archivi vengono creati prima come file temporanei `.part` e pubblicati solo dopo la verifica. Gli incrementali contengono il manifesto completo dello stato, i file modificati, i file eliminati e il riferimento all’archivio precedente; gli incrementali non vengono rimossi singolarmente per non spezzare la catena. Se non ci sono variazioni, Kopia registra uno skip senza creare un archivio duplicato.

### SHA-256 e integrità

La verifica SHA-256 avviene in più punti:

- dopo ogni download viene calcolato l’hash del file temporaneo ricevuto;
- viene controllata anche la dimensione dichiarata dal server FTP, quando disponibile;
- l’originale locale viene scritto in modo atomico e ricontrollato prima di essere considerato valido;
- ogni file inserito nello ZIP viene registrato nel manifesto con percorso, dimensione e SHA-256;
- il file ZIP viene testato e il manifesto viene ricalcolato durante la verifica;
- la copia secondaria viene promossa solo se il suo SHA-256 coincide con l’archivio originale;
- i PDF sostitutivi vengono caricati su un nome remoto temporaneo, verificati, promossi e verificati nuovamente; in caso di errore viene ripristinato il file precedente.

Il risultato di ogni ciclo include gli hash degli archivi, i conteggi dei file modificati e cancellati e lo stato delle singole operazioni.

### Log, stato e report

Ogni progetto ha una directory **Log** dedicata. Kopia scrive:

- un log generale in `~/Library/Application Support/Kopia/general.log`;
- un log dettagliato per ogni ciclo nella directory Log del progetto;
- report JSON dell’ultimo ciclo e dello storico in `state/`;
- stato live con fase corrente, file in elaborazione, conteggi, tempi e errori;
- eventi distinti per scansione, download, compressione, upload, conversione TIFF, backup, copia secondaria e retention.

I report permettono di distinguere un ciclo completato, un ciclo con errori parziali e un ciclo fallito. Un lock per progetto impedisce l’esecuzione contemporanea di due cicli sullo stesso storage.

## Sicurezza

- La cancellazione remota è disattivata per impostazione predefinita.
- Per abilitarla è necessario usare una sottocartella FTP e confermare scrivendo esattamente `CANCELLA REMOTO`.
- I file vengono verificati tramite SHA256 durante trasferimento e backup.
- Gli originali locali non vengono sovrascritti se lo stato registrato non corrisponde.
- I backup e le cartelle di storage devono essere separati e non annidati.

## Test

```zsh
.venv/bin/python -m unittest discover -s tests -v
```

## Struttura del progetto

```text
main.py                  Avvio GUI e modalità ciclo
runner.py                Esecuzione CLI di un ciclo
kopia/core/       FTP, pipeline, backup, PDF/TIFF e automazioni
kopia/gui/        Interfaccia Tk macOS
kopia/models/     Modelli e validazione dei progetti
tests/                   Test funzionali e controlli di sicurezza
install_mac.sh           Installazione dipendenze
start_mac.command        Avvio applicazione
build_mac.sh             Test e build .app
```

## Licenza

Il progetto non include ancora una licenza pubblica. Aggiungi un file `LICENSE` prima di distribuire o riutilizzare il codice.
