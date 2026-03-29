package main

import (
	"fmt"
	"io"
	"os"
	"strings"
)

const (
	bannerRedTrue    = "\033[38;2;226;75;74m"
	bannerRoseTrue   = "\033[38;2;240;149;149m"
	bannerBlushTrue  = "\033[38;2;247;193;193m"
	bannerIvoryTrue  = "\033[38;2;252;235;235m"
	bannerShadowTrue = "\033[38;2;42;8;8m"
	bannerWineTrue   = "\033[38;2;121;31;31m"
	bannerDeepTrue   = "\033[38;2;80;19;19m"

	bannerRed256    = "\033[38;5;203m"
	bannerRose256   = "\033[38;5;210m"
	bannerBlush256  = "\033[38;5;224m"
	bannerIvory256  = "\033[38;5;231m"
	bannerShadow256 = "\033[38;5;52m"
	bannerWine256   = "\033[38;5;88m"
	bannerDeep256   = "\033[38;5;52m"

	bannerRedANSI    = "\033[91m"
	bannerRoseANSI   = "\033[91m"
	bannerBlushANSI  = "\033[97m"
	bannerIvoryANSI  = "\033[97m"
	bannerShadowANSI = "\033[90m"
	bannerWineANSI   = "\033[31m"
	bannerDeepANSI   = "\033[2;31m"
)

type bannerTheme struct {
	red    string
	rose   string
	blush  string
	ivory  string
	shadow string
	wine   string
	deep   string
}

var ghostPixels = [][]int{
	{0, 0, 0, 1, 1, 1, 1, 0, 0, 0},
	{0, 0, 1, 1, 2, 2, 1, 1, 0, 0},
	{0, 1, 1, 2, 3, 3, 2, 1, 1, 0},
	{0, 1, 2, 4, 3, 3, 4, 2, 1, 0},
	{0, 1, 4, 4, 3, 3, 4, 4, 1, 0},
	{0, 2, 3, 3, 1, 1, 3, 3, 2, 0},
	{1, 2, 3, 3, 3, 3, 3, 3, 2, 1},
	{1, 1, 2, 2, 2, 2, 2, 2, 1, 1},
	{1, 1, 3, 3, 3, 3, 3, 3, 1, 1},
	{1, 1, 1, 2, 3, 3, 2, 1, 1, 1},
	{0, 1, 1, 2, 2, 2, 2, 1, 1, 0},
	{0, 1, 1, 1, 1, 1, 1, 1, 1, 0},
	{0, 5, 1, 1, 1, 1, 1, 1, 5, 0},
	{0, 5, 0, 1, 1, 1, 0, 5, 0, 0},
	{0, 6, 0, 0, 5, 0, 0, 6, 0, 0},
}

var ghostDisplayRows = []int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14}

var wordOrder = []string{"W", "e", "b", "G", "h", "o", "s", "t", "i", "n", "g"}

var wordGlyphs = map[string][][]int{
	"W": {
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 1, 0, 1},
		{1, 0, 1, 0, 1},
		{1, 1, 0, 1, 1},
		{1, 0, 0, 0, 1},
	},
	"e": {
		{0, 0, 0, 0, 0},
		{0, 0, 0, 0, 0},
		{0, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 1, 1, 1, 1},
		{1, 0, 0, 0, 0},
		{0, 1, 1, 1, 0},
	},
	"b": {
		{1, 0, 0, 0, 0},
		{1, 0, 0, 0, 0},
		{1, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 1, 1, 1, 0},
	},
	"G": {
		{0, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 0},
		{1, 0, 1, 1, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{0, 1, 1, 1, 0},
	},
	"h": {
		{1, 0, 0, 0, 0},
		{1, 0, 0, 0, 0},
		{1, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
	},
	"o": {
		{0, 0, 0, 0, 0},
		{0, 0, 0, 0, 0},
		{0, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{0, 1, 1, 1, 0},
	},
	"s": {
		{0, 0, 0, 0, 0},
		{0, 0, 0, 0, 0},
		{0, 1, 1, 1, 1},
		{1, 0, 0, 0, 0},
		{0, 1, 1, 1, 0},
		{0, 0, 0, 0, 1},
		{1, 1, 1, 1, 0},
	},
	"t": {
		{0, 1, 0, 0, 0},
		{0, 1, 0, 0, 0},
		{1, 1, 1, 1, 1},
		{0, 1, 0, 0, 0},
		{0, 1, 0, 0, 0},
		{0, 1, 0, 0, 0},
		{0, 0, 1, 1, 0},
	},
	"i": {
		{0, 0, 1, 0, 0},
		{0, 0, 0, 0, 0},
		{0, 1, 1, 0, 0},
		{0, 0, 1, 0, 0},
		{0, 0, 1, 0, 0},
		{0, 0, 1, 0, 0},
		{0, 1, 1, 1, 0},
	},
	"n": {
		{0, 0, 0, 0, 0},
		{0, 0, 0, 0, 0},
		{1, 1, 1, 1, 0},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
		{1, 0, 0, 0, 1},
	},
	"g": {
		{0, 0, 0, 0, 0},
		{0, 0, 0, 0, 0},
		{0, 1, 1, 1, 1},
		{1, 0, 0, 0, 1},
		{0, 1, 1, 1, 1},
		{0, 0, 0, 0, 1},
		{1, 1, 1, 1, 0},
	},
}

func PrintLaunchBanner(w io.Writer) {
	const baseIndent = "  "
	const blockGap = "    "
	const letterGap = 1
	const ghostXScale = 2
	theme := currentBannerTheme()

	fmt.Fprintln(w)

	leftLines := renderIndexedArt(ghostPixels, ghostDisplayRows, ghostPalette(theme), ghostXScale)
	rightLines := renderRightBlock(letterGap, len(leftLines), wordColors(theme))
	leftWidth := ghostRenderWidth(len(ghostPixels[0]), ghostXScale)

	totalLines := len(leftLines)
	if len(rightLines) > totalLines {
		totalLines = len(rightLines)
	}

	for i := 0; i < totalLines; i++ {
		left := strings.Repeat(" ", leftWidth)
		if i < len(leftLines) {
			left = leftLines[i]
		}

		right := ""
		if i < len(rightLines) {
			right = rightLines[i]
		}

		fmt.Fprintf(w, "%s%s%s%s\n", baseIndent, left, blockGap, right)
	}
	fmt.Fprintln(w)
}

func currentBannerTheme() bannerTheme {
	colorterm := strings.ToLower(os.Getenv("COLORTERM"))
	term := strings.ToLower(os.Getenv("TERM"))
	termProgram := strings.ToLower(os.Getenv("TERM_PROGRAM"))
	forcedMode := strings.ToLower(strings.TrimSpace(os.Getenv("WEBGHOSTING_BANNER_COLOR_MODE")))

	switch forcedMode {
	case "truecolor":
		return bannerTheme{
			red:    bannerRedTrue,
			rose:   bannerRoseTrue,
			blush:  bannerBlushTrue,
			ivory:  bannerIvoryTrue,
			shadow: bannerShadowTrue,
			wine:   bannerWineTrue,
			deep:   bannerDeepTrue,
		}
	case "256", "256color":
		return bannerTheme{
			red:    bannerRed256,
			rose:   bannerRose256,
			blush:  bannerBlush256,
			ivory:  bannerIvory256,
			shadow: bannerShadow256,
			wine:   bannerWine256,
			deep:   bannerDeep256,
		}
	case "ansi":
		return bannerTheme{
			red:    bannerRedANSI,
			rose:   bannerRoseANSI,
			blush:  bannerBlushANSI,
			ivory:  bannerIvoryANSI,
			shadow: bannerShadowANSI,
			wine:   bannerWineANSI,
			deep:   bannerDeepANSI,
		}
	}

	// Apple Terminal often advertises modern color support but can render
	// these truecolor sequences inconsistently with some profiles.
	if termProgram != "apple_terminal" && (strings.Contains(colorterm, "truecolor") || strings.Contains(colorterm, "24bit") || strings.Contains(term, "direct")) {
		return bannerTheme{
			red:    bannerRedTrue,
			rose:   bannerRoseTrue,
			blush:  bannerBlushTrue,
			ivory:  bannerIvoryTrue,
			shadow: bannerShadowTrue,
			wine:   bannerWineTrue,
			deep:   bannerDeepTrue,
		}
	}

	if strings.Contains(term, "256") || termProgram == "apple_terminal" || (term != "" && term != "dumb") {
		return bannerTheme{
			red:    bannerRed256,
			rose:   bannerRose256,
			blush:  bannerBlush256,
			ivory:  bannerIvory256,
			shadow: bannerShadow256,
			wine:   bannerWine256,
			deep:   bannerDeep256,
		}
	}

	return bannerTheme{
		red:    bannerRedANSI,
		rose:   bannerRoseANSI,
		blush:  bannerBlushANSI,
		ivory:  bannerIvoryANSI,
		shadow: bannerShadowANSI,
		wine:   bannerWineANSI,
		deep:   bannerDeepANSI,
	}
}

func ghostPalette(theme bannerTheme) []string {
	return []string{
		"",
		theme.red,
		theme.rose,
		theme.ivory,
		theme.shadow,
		theme.wine,
		theme.deep,
	}
}

func wordColors(theme bannerTheme) map[string]string {
	return map[string]string{
		"W": theme.ivory,
		"e": theme.blush,
		"b": theme.blush,
		"G": theme.red,
		"h": theme.red,
		"o": theme.red,
		"s": theme.rose,
		"t": theme.rose,
		"i": theme.rose,
		"n": theme.red,
		"g": theme.red,
	}
}

func renderIndexedArt(matrix [][]int, rowOrder []int, palette []string, xScale int) []string {
	lines := make([]string, 0, len(rowOrder))
	for _, rowIndex := range rowOrder {
		row := matrix[rowIndex]
		var line strings.Builder
		for _, px := range row {
			if px == 0 {
				line.WriteString(strings.Repeat(" ", xScale))
			} else {
				line.WriteString(palette[px])
				line.WriteString(strings.Repeat("█", xScale))
				line.WriteString(ColorReset)
			}
		}
		lines = append(lines, line.String())
	}
	return lines
}

func renderWordmark(letterGap int, colors map[string]string) []string {
	const rows = 7
	lines := make([]string, 0, (rows+1)/2)

	for row := 0; row < rows; row += 2 {
		var line strings.Builder
		for i, glyphName := range wordOrder {
			glyph := wordGlyphs[glyphName]
			color := colors[glyphName]
			for col := 0; col < len(glyph[row]); col++ {
				topOn := glyph[row][col] != 0
				bottomOn := row+1 < rows && glyph[row+1][col] != 0
				line.WriteString(renderGlyphPair(topOn, bottomOn, color))
			}
			if i < len(wordOrder)-1 {
				line.WriteString(strings.Repeat(" ", letterGap))
			}
		}
		lines = append(lines, line.String())
	}

	return lines
}

func renderGlyphPair(topOn, bottomOn bool, color string) string {
	switch {
	case topOn && bottomOn:
		return color + "█" + ColorReset
	case topOn:
		return color + "▀" + ColorReset
	case bottomOn:
		return color + "▄" + ColorReset
	default:
		return " "
	}
}

func renderRightBlock(letterGap, targetHeight int, colors map[string]string) []string {
	wordmark := renderWordmark(letterGap, colors)
	if targetHeight <= len(wordmark) {
		return wordmark
	}

	wordWidth := wordmarkWidth(letterGap)
	topPad := (targetHeight - len(wordmark)) / 2
	lines := make([]string, 0, targetHeight)
	for i := 0; i < topPad; i++ {
		lines = append(lines, strings.Repeat(" ", wordWidth))
	}
	lines = append(lines, wordmark...)
	return lines
}

func wordmarkWidth(letterGap int) int {
	width := 0
	for i, glyphName := range wordOrder {
		glyph := wordGlyphs[glyphName]
		if len(glyph) == 0 {
			continue
		}
		width += len(glyph[0])
		if i < len(wordOrder)-1 {
			width += letterGap
		}
	}
	return width
}

func ghostRenderWidth(cols, xScale int) int {
	if cols == 0 {
		return 0
	}
	return cols * xScale
}

func centerOffset(totalWidth, contentWidth int) int {
	if contentWidth >= totalWidth {
		return 0
	}
	return (totalWidth - contentWidth) / 2
}
