#!/usr/bin/env python3
import sys
from datetime import datetime
from dateutil.parser import parse as parseDT
import requests
import shlex
import datetime


GH_API_BASE = "https://api.github.com/"


class DownloadTarget:
	def __init__(self, name: str, version: str, prerelease: bool, created: datetime, published: datetime, fileCreated: datetime, fileModified: datetime, uri: str):
		self.name = name
		self.version = version
		self.prerelease = prerelease
		self.created = created
		self.published = published
		self.fileCreated = fileCreated
		self.fileModified = fileModified
		self.uri = uri

	def cmpTuple(self):
		return (self.created, self.published, self.fileCreated, self.fileModified)

	def __str__(self):
		return self.name + " (" + self.version + ", " + ("pre" if self.prerelease else "") + "release, " + str(self.fileCreated) + ") <" + self.uri + ">"

	def __lt__(self, other):
		return self.cmpTuple() < other.cmpTuple()

	def __gt__(self, other):
		return self.cmpTuple() > other.cmpTuple()

	def __eq__(self, other):
		return self.cmpTuple() == other.cmpTuple()


def getTargets(repoPath, titleRx, tagRx, downloadFileNameRx):
	RELEASES_EP = GH_API_BASE + "repos/" + repoPath + "/releases"

	req = requests.get(RELEASES_EP)
	headers = requests.utils.default_headers()
	headers["User-Agent"] = "LatestReleaseRetriever"
	h = req.headers
	limitRemaining = int(h["X-RateLimit-Remaining"])
	limitTotal = int(h["X-RateLimit-Limit"])
	limitResetTime = datetime.datetime.utcfromtimestamp(int(h["X-RateLimit-Reset"]))

	print(limitRemaining, "/", limitTotal, str((limitRemaining / limitTotal)*100.)+"%", "limit will be reset:", limitResetTime, "in", limitResetTime - datetime.datetime.now())

	t = req.json()

	if isinstance(t, dict) and "message" in t:
		raise Exception(t["message"])

	for r in t:
		nm = r["name"]
		if not titleRx.match(nm):
			continue
		tagMatch = tagRx.match(r["tag_name"])

		if not tagMatch:
			continue

		pr = r["prerelease"]
		v = tagMatch.group(1)
		c = parseDT(r["created_at"])
		p = parseDT(r["published_at"])
		for a in r["assets"]:
			if not downloadFileNameRx.match(a["name"]):
				continue
			fc = parseDT(a["created_at"])
			m = parseDT(a["updated_at"])
			yield DownloadTarget(nm, v, pr, c, p, fc, m, a["browser_download_url"])
