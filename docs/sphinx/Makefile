# Makefile for Sphinx documentation

# You can set these variables from the command line.
SPHINXOPTS    = -W
SPHINXBUILD   = python3 -msphinx
SOURCEDIR     = source
BUILDDIR      = build

.PHONY: help clean clean-html clean-man Makefile

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

clean-html:
	@ls -1 "$(BUILDDIR)/html/" | xargs -I {} rm -rf "$(BUILDDIR)/html/{}"

clean-man:
	@ls -1 "$(BUILDDIR)/man/" | xargs -I {} rm -rf "$(BUILDDIR)/man/{}"

# Clean the build directory
clean: clean-html clean-man

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
