---
reference_type: formatting-standards
description: BibTeX formatting rules, journal abbreviations, and arXiv ID formats
used_by: [gpd-bibliographer]
---

# BibTeX Formatting Standards

## BibTeX Entry Types

```bibtex
% Journal article (most common in physics)
@article{Maldacena:1997re,
    author = "Maldacena, Juan Martin",
    title = "{The Large N limit of superconformal field theories and supergravity}",
    eprint = "hep-th/9711200",
    archivePrefix = "arXiv",
    doi = "10.1023/A:1026654312961",
    journal = "Int. J. Theor. Phys.",
    volume = "38",
    pages = "1113--1133",
    year = "1999"
}

% Preprint (not yet published)
@article{Author:2024abc,
    author = "Author, First and Author, Second",
    title = "{Title of the preprint}",
    eprint = "2401.12345",
    archivePrefix = "arXiv",
    primaryClass = "hep-th",
    month = "1",
    year = "2024",
    note = "preprint"
}

% Book
@book{Peskin:1995ev,
    author = "Peskin, Michael E. and Schroeder, Daniel V.",
    title = "{An Introduction to quantum field theory}",
    isbn = "978-0-201-50397-5",
    publisher = "Addison-Wesley",
    address = "Reading, USA",
    year = "1995"
}

% Chapter in a book
@incollection{Weinberg:1979sa,
    author = "Weinberg, Steven",
    title = "{Ultraviolet divergences in quantum theories of gravitation}",
    booktitle = "{General Relativity: An Einstein Centenary Survey}",
    editor = "Hawking, S. W. and Israel, W.",
    pages = "790--831",
    publisher = "Cambridge University Press",
    year = "1980"
}

% Conference proceedings
@inproceedings{Speaker:2023conf,
    author = "Speaker, Name",
    title = "{Title of the talk}",
    booktitle = "{Proceedings of Conference Name}",
    year = "2023",
    eprint = "2301.00000",
    archivePrefix = "arXiv",
    primaryClass = "hep-ph"
}

% PhD thesis
@phdthesis{Student:2023phd,
    author = "Student, Name",
    title = "{Title of the thesis}",
    school = "University Name",
    year = "2023",
    eprint = "2301.00000",
    archivePrefix = "arXiv"
}

% Software
@misc{Johansson:2012qutip,
    author = "Johansson, J. R. and Nation, P. D. and Nori, Franco",
    title = "{QuTiP: An open-source Python framework for the dynamics of open quantum systems}",
    doi = "10.1016/j.cpc.2012.02.021",
    journal = "Comput. Phys. Commun.",
    volume = "183",
    pages = "1760--1772",
    year = "2012"
}
```

## Journal Abbreviation Standards

Use INSPIRE-HEP standard abbreviations:

| Full Name                                         | Abbreviation                |
| ------------------------------------------------- | --------------------------- |
| Physical Review Letters                           | Phys. Rev. Lett.            |
| Physical Review D                                 | Phys. Rev. D                |
| Physical Review B                                 | Phys. Rev. B                |
| Physical Review A                                 | Phys. Rev. A                |
| Physical Review X                                 | Phys. Rev. X                |
| Journal of High Energy Physics                    | JHEP                        |
| Nuclear Physics B                                 | Nucl. Phys. B               |
| Physics Letters B                                 | Phys. Lett. B               |
| Communications in Mathematical Physics            | Commun. Math. Phys.         |
| Annals of Physics                                 | Annals Phys.                |
| Classical and Quantum Gravity                     | Class. Quant. Grav.         |
| Journal of Mathematical Physics                   | J. Math. Phys.              |
| International Journal of Theoretical Physics      | Int. J. Theor. Phys.        |
| Reviews of Modern Physics                         | Rev. Mod. Phys.             |
| Nature Physics                                    | Nature Phys.                |
| The Astrophysical Journal                         | Astrophys. J.               |
| Monthly Notices of the Royal Astronomical Society | Mon. Not. Roy. Astron. Soc. |
| Journal of Cosmology and Astroparticle Physics    | JCAP                        |
| Computer Physics Communications                   | Comput. Phys. Commun.       |
| New Journal of Physics                            | New J. Phys.                |
| Progress of Theoretical and Experimental Physics  | PTEP                        |
| European Physical Journal C                       | Eur. Phys. J. C             |
| Science                                           | Science                     |
| Nature                                            | Nature                      |

## Journal-Specific Formatting Requirements

**Physical Review (APS) journals:**

- Use REVTeX 4.2 bibliography style
- `\bibliographystyle{apsrev4-2}`
- Author format: "Surname, Initials"
- Title in quotes, journal abbreviated

**JHEP:**

- Uses JHEP bibliography style
- `\bibliographystyle{JHEP}`
- Include eprint for all arXiv papers
- INSPIRE texkeys preferred as citation keys

**Nature / Science:**

- Numbered references in order of appearance
- No title in bibliography (Nature) or abbreviated title (Science)
- Very compact format

**Default (when journal not specified):**

- Use INSPIRE-style formatting
- Include all available identifiers (DOI, arXiv, INSPIRE texkey)
- Full title in braces

## Citation Key Conventions

**INSPIRE texkey format (preferred for HEP):**

```
FirstAuthor:YYYYxx
```

Where `xx` is a 2-letter disambiguator. Examples:

- `Maldacena:1997re`
- `Witten:1998qj`
- `Polchinski:1998rq`

**ADS bibcode format (for astrophysics):**

```
YYYYJournVolPageFirstAuthorInitial
```

Example: `1998ApJ...500..525S`

**Custom format (when neither available):**

```
FirstAuthorSurname:YYYYtopic
```

Example: `Mermin:1966fe` (using first two letters of a distinctive title word)

## arXiv ID Formatting

**Old format (before April 2007):**

```bibtex
eprint = "hep-th/9711200",
archivePrefix = "arXiv",
```

Categories: `hep-th`, `hep-ph`, `hep-lat`, `hep-ex`, `gr-qc`, `astro-ph`, `cond-mat`, `nucl-th`, `nucl-ex`, `quant-ph`, `math-ph`, `nlin`, `physics`

**New format (April 2007+):**

```bibtex
eprint = "0704.0001",
archivePrefix = "arXiv",
primaryClass = "hep-th",
```

The `primaryClass` field identifies the category.

**Validation patterns:**

```
Old: [a-z-]+/[0-9]{7}          (e.g., hep-th/9711200)
New: [0-9]{4}\.[0-9]{4,5}      (e.g., 2301.12345)
```
