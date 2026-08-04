# frozen_string_literal: true

require "digest"

# `asset_url` — relative_url plus a content hash, so a deployed asset can never
# be served stale.
#
# Why this exists: the site sits behind Cloudflare, which caches .js and .css at
# the edge for four hours (max-age=14400) while HTML is served DYNAMIC with a ten
# minute max-age. After a deploy that skew means new HTML can be paired with an
# asset from the previous build. That is not theoretical — it shipped a scorecard
# whose HTML had the slate controls while the cached scorecard.js was the version
# before slates existed, so the markup was there and nothing revealed it.
#
# Appending a hash of the file's contents puts each version at its own URL.
# Cloudflare's cache key includes the query string, so a changed file is a cache
# miss and an unchanged one keeps its cache — which is the reason for hashing
# content rather than stamping site.time: the nightly data-only sync rebuilds the
# site without touching the scripts, and there is no reason for every reader to
# re-download them because a candidate's name changed.
#
# Handles both kinds of asset the site serves:
#
#   Static files (the scripts) — the source file IS the deployed file, so its own
#   contents are the hash.
#
#   Compiled stylesheets (/assets/css/main.css) — no such file exists in the
#   source. It is built from assets/css/main.scss plus the partials in _sass/, so
#   hashing "the file" is impossible and hashing only main.scss would miss every
#   change made in a partial, which is the common case. Instead the whole input
#   set is hashed: the entry stylesheet and every partial that could feed it.
#
# Hashing inputs rather than compiled output is a deliberate trade. Getting the
# real output would mean reaching into Jekyll's converted pages mid-render, whose
# ordering is not guaranteed. The input set is cheap and deterministic, and it
# fails in the safe direction: every change that can alter the CSS changes the
# hash. The cost is the occasional needless bust — editing a `//` comment in a
# partial changes an input without changing the output — which costs one
# re-download of one file.
module LivableCrd
  module AssetUrl
    include Jekyll::Filters::URLFilters

    HASH_LENGTH = 8
    SASS_EXTENSIONS = %w[.scss .sass].freeze
    DEFAULT_SASS_DIR = "_sass"

    def asset_url(path)
      # relative_url is Jekyll's own, so baseurl handling stays identical to
      # every other link on the site (deploy.yml passes --baseurl).
      url = relative_url(path)
      digest = asset_digest(path)
      digest ? "#{url}?v=#{digest}" : url
    end

    private

    # Returns nil when there is nothing to hash, which leaves the URL
    # unversioned rather than raising: a typo'd path should surface as the 404 it
    # already is, not as a failed build whose message is about hashing.
    def asset_digest(path)
      site = @context.registers[:site]
      return nil unless site

      relative = path.to_s.sub(%r{\A/}, "")
      return nil if relative.empty?

      file = File.join(site.source, relative)
      # MD5 because this is a cache key, not a security boundary; truncated
      # because 8 hex characters is ample to distinguish builds of one file.
      return Digest::MD5.file(file).hexdigest[0, HASH_LENGTH] if File.file?(file)

      digest_of(sass_inputs(site, relative))
    end

    # The entry stylesheet for a compiled path, plus every partial under
    # sass_dir. Over-inclusive on purpose: resolving which partials a given entry
    # actually @uses would mean parsing Sass, and this site has one stylesheet,
    # so the only cost of hashing them all is a needless bust when an unused
    # partial changes.
    def sass_inputs(site, relative)
      base = relative.sub(/\.css\z/, "")
      return [] if base == relative # not a stylesheet path at all

      entry = SASS_EXTENSIONS
              .map { |ext| File.join(site.source, "#{base}#{ext}") }
              .find { |candidate| File.file?(candidate) }
      return [] unless entry

      sass_dir = site.config.dig("sass", "sass_dir") || DEFAULT_SASS_DIR
      partials = Dir.glob(File.join(site.source, sass_dir, "**", "*.{scss,sass}")).sort

      [entry] + partials
    end

    # Names go into the digest alongside contents: renaming a partial can change
    # the compiled output (@use order, or a partial dropping out of the build)
    # while leaving the set of bytes on disk identical.
    def digest_of(files)
      return nil if files.empty?

      md5 = Digest::MD5.new
      files.each do |file|
        md5 << File.basename(file)
        md5.file(file)
      end
      md5.hexdigest[0, HASH_LENGTH]
    end
  end
end

Liquid::Template.register_filter(LivableCrd::AssetUrl)
