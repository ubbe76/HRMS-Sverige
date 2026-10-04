"""Tidsregler för OB och övertid: ren intervallräkning utan databas."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import pairwise

OB = "OB"
OVERTID = "Övertid"

Intervall = tuple[datetime, datetime]


@dataclass(frozen=True)
class Tidsregel:
	typ: str
	niva: int
	dagar: frozenset[int]  # date.weekday(): måndag = 0
	helgdag: bool
	fran: time
	till: time


def regelintervall(regel: Tidsregel, dag: date, ar_helgdag: bool) -> list[Intervall]:
	"""Regelns period den dagen. Till <= Från går över midnatt; Från = Till är hela dygnet."""
	if dag.weekday() not in regel.dagar and not (ar_helgdag and regel.helgdag):
		return []
	start = datetime.combine(dag, regel.fran)
	slut = datetime.combine(dag, regel.till)
	if slut <= start:
		slut += timedelta(days=1)
	return [(start, slut)]


def timmar(intervall: list[Intervall]) -> float:
	return sum((slut - start).total_seconds() for start, slut in intervall) / 3600


def fordela(
	intervall: list[Intervall],
	regler: list[Tidsregel],
	helgdagar: set[date],
	standardniva: int | None = None,
) -> dict[int, float]:
	"""Timmar per nivå. Högsta nivån gäller där regler överlappar; tid utan regel får standardnivån."""
	resultat: dict[int, float] = {}
	for start, slut in intervall:
		fonster = []
		dag = start.date() - timedelta(days=1)  # regler från dagen före kan gå över midnatt
		while dag <= slut.date():
			for regel in regler:
				for f_start, f_slut in regelintervall(regel, dag, dag in helgdagar):
					if f_start < slut and f_slut > start:
						fonster.append((max(f_start, start), min(f_slut, slut), regel.niva))
			dag += timedelta(days=1)
		punkter = sorted({start, slut, *(f[0] for f in fonster), *(f[1] for f in fonster)})
		for a, b in pairwise(punkter):
			nivaer = [niva for f_start, f_slut, niva in fonster if f_start <= a and f_slut >= b]
			niva = max(nivaer) if nivaer else standardniva
			if niva is not None:
				resultat[niva] = resultat.get(niva, 0.0) + (b - a).total_seconds() / 3600
	return resultat


def extra_tid(arbetat: Intervall, skift: Intervall | None) -> list[Intervall]:
	"""Arbetad tid utanför det planerade skiftet. Utan skift finns ingen extra tid."""
	if not skift:
		return []
	in_tid, ut_tid = arbetat
	s_start, s_slut = skift
	extra = []
	if in_tid < min(ut_tid, s_start):
		extra.append((in_tid, min(ut_tid, s_start)))
	if max(in_tid, s_slut) < ut_tid:
		extra.append((max(in_tid, s_slut), ut_tid))
	return extra


def dela_av_raster(intervall: list[Intervall], raster: list[Intervall]) -> list[Intervall]:
	"""Arbetad tid utan obetalda raster. En stämplad rast ligger redan utanför passen och dras inte två gånger."""
	kvar = list(intervall)
	for r_start, r_slut in raster:
		delar = []
		for start, slut in kvar:
			if start < min(slut, r_start):
				delar.append((start, min(slut, r_start)))
			if max(start, r_slut) < slut:
				delar.append((max(start, r_slut), slut))
		kvar = delar
	return kvar


def dela_mertid(
	extra: list[Intervall], inom_skift_timmar: float, tak_timmar: float
) -> tuple[list[Intervall], list[Intervall]]:
	"""Delar den extra tiden i mertid (tidigast först, upp till taket) och övertid."""
	kvar = timedelta(hours=max(0.0, tak_timmar - inom_skift_timmar))
	mertid, overtid = [], []
	for start, slut in sorted(extra):
		langd = slut - start
		if kvar >= langd:
			mertid.append((start, slut))
			kvar -= langd
		elif kvar > timedelta(0):
			mertid.append((start, start + kvar))
			overtid.append((start + kvar, slut))
			kvar = timedelta(0)
		else:
			overtid.append((start, slut))
	return mertid, overtid
