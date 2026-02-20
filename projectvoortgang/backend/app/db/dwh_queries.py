"""SQL queries for reading from client Data Warehouse (PostgreSQL).

These queries target the Syntess SSM schema in the client's PostgreSQL DWH.
Table names and column names follow the SSM conventions.

NOTE: These queries will need to be adjusted per client DWH schema.
The column mappings below are based on the Beck & v.d. Kroef DWH structure.
"""

# Top-level projects (Niveau 1)
QUERY_HOOFDPROJECTEN = """
SELECT DISTINCT
    p."HoofdProjectKey" as project_key,
    p."Projectnaam" as project_naam,
    p."Projectfase" as projectfase,
    1 as projectniveau,
    p."Startdatum"::date as start_boekdatum,
    p."Einddatum"::date as einde_boekdatum
FROM notifica."SSM Projecten" p
WHERE p."Niveau" = 1
  AND p."Status" = 'Open'
ORDER BY p."Projectnaam"
"""

# Sub-projects (Niveau 2 & 3) for a given hoofdproject
QUERY_DEELPROJECTEN = """
SELECT DISTINCT
    p."ProjectKey" as project_key,
    p."Projectnaam" as project_naam,
    p."Projectfase" as projectfase,
    p."Niveau" as projectniveau,
    p."HoofdProjectKey" as hoofdproject_key
FROM notifica."SSM Projecten" p
WHERE p."HoofdProjectKey" = %(hoofdproject_key)s
  AND p."Niveau" > 1
ORDER BY p."Niveau", p."Projectnaam"
"""

# Bestekparagrafen at specified level
QUERY_BESTEKPARAGRAFEN = """
SELECT DISTINCT
    bp."BestekParagraafKey" as bestekparagraaf_key,
    bp."Bestekparagraaf" as bestekparagraaf,
    bp."Bestekparagraaf niveau" as bestekparagraafniveau
FROM notifica."SSM Bestekparagrafen" bp
JOIN notifica."SSM Projecten" p ON bp."ProjectKey" = p."ProjectKey"
WHERE p."HoofdProjectKey" = %(project_key)s
  AND bp."Bestekparagraaf niveau" = %(niveau)s
ORDER BY bp."Bestekparagraaf"
"""

# Full project data - all costs, hours, requests per bestekparagraaf
# This is the main query that replaces the Power BI dataset
QUERY_PROJECTDATA = """
SELECT
    p."ProjectKey" as project_key,
    p."Projectnaam" as project_naam,
    p."Niveau" as projectniveau,
    p."Projectfase" as projectfase,
    bp."BestekParagraafKey" as bestekparagraaf_key,
    bp."Bestekparagraaf" as bestekparagraaf,
    bp."Bestekparagraaf niveau" as bestekparagraafniveau,

    -- Calculatie kostprijzen
    COALESCE(ck."Kostprijs inkoop", 0) as calculatie_kostprijs_inkoop,
    COALESCE(ck."Kostprijs arbeid montage", 0) as calculatie_kostprijs_arbeid_montage,
    COALESCE(ck."Kostprijs arbeid projectgebonden", 0) as calculatie_kostprijs_arbeid_projectgebonden,

    -- Calculatie verrekenprijzen
    COALESCE(cv."Verrekenprijs inkoop", 0) as calculatie_verrekenprijs_inkoop,
    COALESCE(cv."Verrekenprijs arbeid montage", 0) as calculatie_verrekenprijs_arbeid_montage,
    COALESCE(cv."Verrekenprijs arbeid projectgebonden", 0) as calculatie_verrekenprijs_arbeid_projectgebonden,

    -- Calculatie uren
    COALESCE(cu."Montage uren", 0) as calculatie_montage_uren,
    COALESCE(cu."Projectgebonden uren", 0) as calculatie_projectgebonden_uren,

    -- Definitieve kostprijzen
    COALESCE(dk."Kostprijs inkoop", 0) as definitieve_kostprijs_inkoop,
    COALESCE(dk."Kostprijs arbeid montage", 0) as definitieve_kostprijs_arbeid_montage,
    COALESCE(dk."Kostprijs arbeid projectgebonden", 0) as definitieve_kostprijs_arbeid_projectgebonden,

    -- Definitieve verrekenprijzen
    COALESCE(dv."Verrekenprijs inkoop", 0) as definitieve_verrekenprijs_inkoop,
    COALESCE(dv."Verrekenprijs arbeid montage", 0) as definitieve_verrekenprijs_arbeid_montage,
    COALESCE(dv."Verrekenprijs arbeid projectgebonden", 0) as definitieve_verrekenprijs_arbeid_projectgebonden,

    -- Onverwerkte verrekenprijzen
    COALESCE(ov."Verrekenprijs inkoop", 0) as onverwerkte_verrekenprijs_inkoop,
    COALESCE(ov."Verrekenprijs arbeid montage", 0) as onverwerkte_verrekenprijs_arbeid_montage,
    COALESCE(ov."Verrekenprijs arbeid projectgebonden", 0) as onverwerkte_verrekenprijs_arbeid_projectgebonden,

    -- Gerealiseerde uren
    COALESCE(gu."Montage uren definitief", 0) as montage_uren_definitief,
    COALESCE(gu."Montage uren onverwerkt", 0) as montage_uren_onverwerkt,
    COALESCE(gu."Projectgebonden uren definitief", 0) as projectgebonden_uren_definitief,
    COALESCE(gu."Projectgebonden uren onverwerkt", 0) as projectgebonden_uren_onverwerkt,

    -- Historische verzoeken
    COALESCE(hv."Verzoeken inkoop", 0) as historische_verzoeken_inkoop,
    COALESCE(hv."Verzoeken montage", 0) as historische_verzoeken_montage,
    COALESCE(hv."Verzoeken projectgebonden", 0) as historische_verzoeken_projectgebonden,
    COALESCE(hv."Verzoeken montage uren", 0) as historische_verzoeken_montage_uren,
    COALESCE(hv."Verzoeken projectgebonden uren", 0) as historische_verzoeken_projectgebonden_uren

FROM notifica."SSM Projecten" p
LEFT JOIN notifica."SSM Bestekparagrafen" bp ON bp."ProjectKey" = p."ProjectKey"
LEFT JOIN notifica."SSM Calculatie kostprijzen" ck ON ck."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Calculatie verrekenprijzen" cv ON cv."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Calculatie uren" cu ON cu."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Definitieve kostprijzen" dk ON dk."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Definitieve verrekenprijzen" dv ON dv."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Onverwerkte verrekenprijzen" ov ON ov."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Gerealiseerde uren" gu ON gu."BestekParagraafKey" = bp."BestekParagraafKey"
LEFT JOIN notifica."SSM Historische verzoeken" hv ON hv."BestekParagraafKey" = bp."BestekParagraafKey"
WHERE p."HoofdProjectKey" = %(hoofdproject_key)s
ORDER BY p."Niveau", bp."Bestekparagraaf niveau", bp."Bestekparagraaf"
"""
