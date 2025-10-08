# RegressionTestingOptimizationSLR

Questa repository contiene tutti i dati rilevanti alla Systematic Literature Review su Regression Testing Optimization.
I risultati di ogni step della SLR sono organizzati nelle rispettive cartelle. Inoltre, ogni cartella contiene un file info contenente un riassunto dei risultati dello step a cui si riferisce.

## 1_Citations
Questa cartella è suddivisa in 3 sottocartelle: IEEE, ACM, ScienceDirect, ciascuna contenente i file .bib che raggruppano tutti gli studi ottenuti dalle query eseguite sui rispettivi siti.

## 2_Duplicate Removal
Prima i file .bib, divisi per dataset, sono stati convertiti in Excel e successivamente i duplicati sono stati rimossi; infine, Merged_Studies_No_Duplicates.xlsx contiene tutti i paper ottenuti da tutti i dataset senza duplicati.

## 3_Inclusion Exclusion Criteria
Sulla base dei risultati del passaggio precedente, sono stati applicati gli inclusion criteria, infine gli exclusion criteria. I risultati dei due step sono salvati negli Excel corrispondenti. Il file info descrive nel dettaglio i criteri e riporta le metriche registrate.

## 4_Classification
In questo step, ciascun paper è stato classificato come Systematic Literature Review, Review/Survey, Primary Study.

## 5_Snowballing
Una volta classificati i paper, è stato eseguito backward snowballing. Successivamente forward snowballing. I risultati sono stati uniti, ogni paper incluso durante lo snowballing è stato sottoposto agli inclusion ed exclusion criteria.