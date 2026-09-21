# frozen_string_literal: true

require "rqrcode_core"

# `{{ url | qr_svg }}`: a QR code for that URL as inline SVG.
#
# Used by the print leaflet on a candidate's page, where a sheet handed to
# somebody at a door has to be able to lead them back to the full answers behind
# the grades. Nothing on paper is clickable and the address is long enough that
# nobody will type it, so the code is the only link a leaflet has.
#
# Inline rather than a generated .png or .svg asset. Three reasons, in order:
#
#   - It is exact at any size. A leaflet prints at whatever scale the reader's
#     dialog is set to, and a raster code that is resampled on the way to the
#     paper is a code that does not scan.
#   - There are 210 candidate pages. Written as files, that is 210 assets to
#     generate, commit and keep in step with a candidate list that changes
#     nightly; the URL is derived from the page it sits on and cannot go stale.
#   - Print drops what it cannot fetch in time. An <img> is a second request,
#     and a reader who hits Print before it lands prints a blank square where
#     the code should be.
#
# rqrcode_core is the encoder without renderers, so the SVG below is the whole
# of the drawing code. Level Q (25% recovery) rather than the default M: a
# leaflet is folded, handled and photocopied, and the code is small enough on
# the page that the extra version costs nothing.
module LivableCrd
  module QrCode
    # Modules of white around the code, which the spec requires and every
    # scanner relies on. Drawn into the viewBox rather than left to the page,
    # so a code sitting hard against other ink still scans.
    QUIET_ZONE = 4

    # Same URL on every build of the same page, and the encoder is the expensive
    # part of this filter. Keyed by URL and error level so two different codes
    # cannot collide.
    @cache = {}

    class << self
      attr_reader :cache
    end

    def qr_svg(url, level = "q")
      url = url.to_s.strip
      return "" if url.empty?

      QrCode.cache[[url, level]] ||= build(url, level)
    end

    private

    def build(url, level)
      modules = RQRCodeCore::QRCode.new(url, level: level.to_s.downcase.to_sym).modules
      span = modules.size + (QUIET_ZONE * 2)

      # One subpath per horizontal run of dark modules, rather than one element
      # per module. A version 5 code is 1,369 modules in roughly 360 runs, and
      # this markup is inlined into every one of 210 candidate pages: a <rect>
      # each is ~40KB of page, a <rect> per run ~15KB, and a path subpath per run
      # ~5KB. The shape drawn is identical in all three.
      runs = []
      modules.each_with_index do |row, y|
        x = 0
        while x < row.size
          unless row[x]
            x += 1
            next
          end

          run = 1
          run += 1 while row[x + run]
          runs << "M#{x + QUIET_ZONE} #{y + QUIET_ZONE}h#{run}v1h-#{run}z"
          x += run
        end
      end

      # aria-hidden, and no <title>: the caption beside it says where the code
      # goes, and a screen reader has the same link as real text on the page. An
      # image role here would announce "QR code" to somebody who cannot scan one.
      %(<svg class="qr-code" viewBox="0 0 #{span} #{span}" width="#{span}" height="#{span}" ) +
        %(xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" aria-hidden="true" focusable="false">) +
        %(<rect width="#{span}" height="#{span}" fill="#fff"/>) +
        %(<path fill="#000" d="#{runs.join}"/>) +
        "</svg>"
    end

    module_function :build
  end
end

Liquid::Template.register_filter(LivableCrd::QrCode)
