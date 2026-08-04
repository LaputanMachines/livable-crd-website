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
# Only for STATIC assets, whose source file is also the deployed file. It is
# deliberately not used for /assets/css/main.css: that file is compiled from
# assets/css/main.scss plus everything in _sass/, so hashing the source Jekyll
# sees here would miss every change made in a partial — the common case — and
# quietly imply freshness it cannot deliver.
module LivableCrd
  module AssetUrl
    include Jekyll::Filters::URLFilters

    HASH_LENGTH = 8

    def asset_url(path)
      # relative_url is Jekyll's own, so baseurl handling stays identical to
      # every other link on the site (deploy.yml passes --baseurl).
      url = relative_url(path)

      file = asset_source_path(path)
      return url unless file && File.file?(file)

      # MD5 because this is a cache key, not a security boundary; truncated
      # because 8 hex characters is ample to distinguish builds of one file.
      "#{url}?v=#{Digest::MD5.file(file).hexdigest[0, HASH_LENGTH]}"
    end

    private

    # Missing files fall through to an unversioned URL rather than raising: a
    # typo'd path should surface as the 404 it already is, not as a failed build
    # whose message is about hashing.
    def asset_source_path(path)
      site = @context.registers[:site]
      return nil unless site

      relative = path.to_s.sub(%r{\A/}, "")
      return nil if relative.empty?

      File.join(site.source, relative)
    end
  end
end

Liquid::Template.register_filter(LivableCrd::AssetUrl)
