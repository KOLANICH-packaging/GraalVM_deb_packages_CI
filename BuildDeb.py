#!/usr/bin/env python3
import sys
import struct
import re
import os
from itertools import chain
import warnings
import tarfile

import sh
from tqdm import tqdm

from pydebhelper import *
from getLatestVersionAndURLWithGitHubAPI import getTargets



def genGraalProvides(start=6, end=8):  # java 12 still not supported yet
	graalvmProvides = ["default-jre", "default-jre-headless", "java-compiler"]
	for i in range(start, end + 1):
		si = str(i)
		graalvmProvides += ["openjdk-" + si + "-jre", "openjdk-" + si + "-jre-headless", "java" + si + "-runtime", "java" + si + "-runtime-headless", "java" + si + "-sdk-headless"]
	return graalvmProvides


config = OrderedDict()

config["llvm"] = {
	"descriptionLong": "LLVM engine for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/languages/llvm/",
	"rip": {
		"bin": ["lli"],
		"other": ["jre/languages/llvm"]
	}
}
config["js"] = {
	"descriptionLong": "JavaScript engine & node.js runtime for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/languages/js/",
	"rip": {
		"bin": ["js", "node", "npm"],
		"other": ["jre/languages/js", "jre/lib/graalvm/graaljs-launcher.jar"]
	}
}
config["python"] = {
	"descriptionLong": "python runtime for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/languages/python/",
	"rip": {
		"bin": ["graalpython"],
		"other": ["jre/languages/python", "jre/lib/graalvm/graalpython-launcher.jar", "LICENSE_GRAALPYTHON", "jre/languages/python/LICENSE_GRAALPYTHON"]
	}
}
config["ruby"] = {
	"descriptionLong": "ruby runtime for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/languages/ruby/",
	"rip": {
		"bin": ["truffleruby", "ruby", "bundle", "bundler", "gem", "irb", "rake", "rdoc", "ri"],
		"other": ["jre/languages/ruby", "jre/lib/boot/truffleruby-services.jar", "jre/lib/graalvm/truffleruby-launcher.jar", "LICENSE_TRUFFLERUBY.md", "3rd_party_licenses_truffleruby.txt"]
	}
}
config["r"] = {
	"descriptionLong": "R runtime for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/languages/R/",
	"rip": {
		"bin": ["R", "Rscript"],
		"other": ["jre/languages/R", "LICENSE_FASTR", "3rd_party_licenses_fastr.txt"]
	}
}

config["gu"] = {
	"descriptionLong": "Package manager for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/graal-updater/",
	"rip": {
		"bin": ["gu"],
		"other": ["jre/lib/installer", "bin/gu"]
	}
}
config["polyglot"] = {
	"descriptionLong": "Polyglot for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/polyglot/",
	"rip": {
		"bin": ["polyglot"],
		"other": ["jre/lib/polyglot"]
	}
}
config["samples"] = {
	"descriptionLong": "Example code for GraalVM",
	"homepage": "https://www.graalvm.org/",
	"rip": {
		"other": ["sample"]
	}
}
config["visualvm"] = {
	"descriptionLong": "VisualVM for GraalVM",
	"homepage": "https://www.graalvm.org/docs/reference-manual/tools/#heap-viewer",
	"rip": {
		"bin": ["jvisualvm"],
		"other": ["lib/visualvm"]
	}
}

def removeUnneededSources(unpackedDir):
	for f in chain(unpackedDir.glob("**/src.zip"), unpackedDir.glob("**/*.src.zip")):
		f.unlink()


def ripGraalPackage(unpackedDir, packagesDir, version, maintainer, builtDir):
	mainPackageName = "graalvm"
	systemPrefix = "usr/lib/jvm/graalvm-ce-amd64"

	removeUnneededSources(unpackedDir)

	results = []

	for pkgPostfix, pkgCfg in config.items():
		pkgCfg = type(pkgCfg)(pkgCfg)
		rip = pkgCfg["rip"]
		del pkgCfg["rip"]

		with Package(mainPackageName + "-" + pkgPostfix, packagesDir, version=version, section="java", maintainer=maintainer, builtDir=builtDir, **pkgCfg) as pkg:
			if "other" in rip:
				for el in rip["other"]:
					pkg.rip(unpackedDir / el, systemPrefix + "/" + el)

			if "bin" in rip:
				for el in rip["bin"]:
					a = "bin/" + el
					aUnp = unpackedDir / a
					if aUnp.exists() or aUnp.is_symlink():
						pkg.rip(aUnp, systemPrefix + "/" + a)
					else:
						warnings.warn(str(aUnp) + " doesn't exist")

					b = "jre/" + a
					bUnp = unpackedDir / b
					if aUnp.exists() or aUnp.is_symlink():
						pkg.rip(bUnp, systemPrefix + "/" + b)
					else:
						warnings.warn(str(bUnp) + " doesn't exist")
			results.append(pkg)

	with Package(mainPackageName, packagesDir, version=version, section="java", homepage="https://github.com/oracle/graal/releases", provides=genGraalProvides(), descriptionShort="graalvm", descriptionLong="GraalVM is a high-performance, embeddable, polyglot virtual machine for running applications written in JavaScript, Python, Ruby, R, JVM-based languages like Java, Scala, Kotlin, and LLVM-based languages such as C and C++. \nAdditionally, GraalVM allows efficient interoperability between programming languages and compiling Java applications ahead-of-time into native executables for faster startup time and lower memory overhead.", maintainer=maintainer, builtDir=builtDir) as graalVM:
		graalVM.rip(unpackedDir, systemPrefix)
		results.append(graalVM)

	return results


def isSubdir(parent: Path, child: Path) -> bool:
	parent = parent.absolute().resolve()
	child = child.absolute().resolve().relative_to(parent)
	for p in child.parts:
		if p == "..":
			return False
	return True


def unpack(archPath, extrDir):
	extrDir = extrDir.resolve()
	packedSize = archPath.stat().st_size
	with archPath.open("rb") as arch:
		arch.seek(packedSize - 4)
		unpackedSize = struct.unpack("<I", arch.read(4))[0]

	with tarfile.open(archPath, "r:gz") as arch:
		with tqdm(total=unpackedSize, unit="B", unit_divisor=1024, unit_scale=True) as pb:
			for f in arch:
				fp = (extrDir / f.name).absolute()
				if isSubdir(extrDir, fp):
					if fp.is_file() or fp.is_symlink():
						fp.unlink()
					fp.parent.mkdir(parents=True, exist_ok=True)
					arch.extract(f, extrDir, set_attrs=True)
					pb.set_postfix(file=str(fp.relative_to(extrDir)), refresh=False)
					pb.update(f.size)


currentProcFileDescriptors = Path("/proc") / str(os.getpid()) / "fd"

fj = sh.firejail.bake(noblacklist=str(currentProcFileDescriptors), _fg=True)

aria2c = fj.aria2c.bake(_fg=True, **{"continue": "true", "check-certificate": "true", "enable-mmap": "true", "optimize-concurrent-downloads": "true", "j": 16, "x": 16, "file-allocation": "falloc"})


def download(targets):
	args = []

	for dst, uri in targets.items():
		args += [uri, linesep, " ", "out=", str(dst), linesep]

	pO, pI = os.pipe()
	with os.fdopen(pI, "w") as pIF:
		pIF.write("".join(args))
		pIF.flush()
	try:
		aria2c(**{"input-file": str(currentProcFileDescriptors / str(pO))})
	finally:
		os.close(pO)
		try:
			os.close(pI)
		except:
			pass

vmTagRx = re.compile("^vm-((?:\\d+\\.){2}\\d+(?:-rc\\d+))?$")
vmTitleMarker = "GraalVM Community Edition .+$"
platformMarker = "linux-amd64"
versionFileNameMarker = "[\\w\\.-]+"
releaseFileNameMarker = versionFileNameMarker + "-" + platformMarker


def getLatestGraalVMRelease():
	downloadFileNameRx = re.compile("^" + releaseFileNameMarker + "\\.tar\\.gz$")
	return max(getTargets("oracle/graal", re.compile("^" + vmTitleMarker), vmTagRx, downloadFileNameRx))


def getLatestGraalRuntimeRelease(repoPath):
	downloadFileNameRx = re.compile(".+installable-ce-" + releaseFileNameMarker + "\\.jar$")
	return max(getTargets(repoPath, re.compile(".+- " + vmTitleMarker), vmTagRx, downloadFileNameRx))


def doBuild():
	thisDir = Path(".")

	downloadDir = Path(thisDir / "downloads")
	archPath = Path(downloadDir / "graalvm-github.tar.gz")
	unpackDir = thisDir / "graalvm-unpacked"
	packagesRootsDir = thisDir / "packagesRoots"
	builtDir = thisDir / "packages"
	repoDir = thisDir / "public" / "repo"

	selT = getLatestGraalVMRelease()

	print("Selected release:", selT, file=sys.stderr)

	runtimesRepos = {"python": "graalvm/graalpython", "ruby": "oracle/truffleruby", "R": "oracle/fastr"}

	runtimeReleases = {k: getLatestGraalRuntimeRelease(v) for k, v in runtimesRepos.items()}

	runtimeFiles = {(downloadDir / (k + ".jar")): v.uri for k, v in runtimeReleases.items()}

	downloadTargets = {archPath: selT.uri, **runtimeFiles}

	download(downloadTargets)
	unpack(archPath, unpackDir)
	graalUnpackedRoot = unpackDir / ("graalvm-ce-" + selT.version)

	guCmd = fj.bake(str(graalUnpackedRoot / "bin/gu"), _fg=True)
	guCmd("-L", "install", *runtimeFiles.keys())

	builtDir.mkdir(parents=True, exist_ok=True)

	maintainer = Maintainer()
	pkgs = ripGraalPackage(graalUnpackedRoot, packagesRootsDir, selT.version, maintainer=maintainer, builtDir=builtDir)

	for pkg in pkgs:
		pkg.build()

	with Repo(root=repoDir, descr=maintainer.name+"'s repo for apt with GraalVM binary packages, built from the official builds on GitHub") as r:
		for pkg in pkgs:
			r += pkg
		print(r.packages2add)


if __name__ == "__main__":
	doBuild()
