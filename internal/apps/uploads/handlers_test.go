package uploads

import (
	"net/http/httptest"
	"testing"
)

func TestDetectFileTypeMatchesCategories(t *testing.T) {
	cases := map[string]string{
		"notes.pdf":   "document",
		"grades.xlsx": "spreadsheet",
		"lesson.pptx": "presentation",
		"avatar.png":  "image",
		"lecture.mp4": "video",
		"audio.mp3":   "audio",
		"bundle.zip":  "archive",
		"unknown.bin": "other",
	}
	for fileName, expected := range cases {
		if got := detectFileType(fileName); got != expected {
			t.Errorf("detectFileType(%q) = %q, want %q", fileName, got, expected)
		}
	}
}

func TestMediaURLIsAbsoluteAndDoesNotJoinAgainstAPIPath(t *testing.T) {
	request := httptest.NewRequest("GET", "https://api.kibegi.test/api/v1/uploads/ABC123/", nil)
	app := App{MediaBase: "https://storage.kibegi.test/kibegi-uploads"}
	got := app.mediaURL(request, "uploads/7/notes.pdf")
	if got != "https://storage.kibegi.test/kibegi-uploads/uploads/7/notes.pdf" {
		t.Fatalf("unexpected media URL: %v", got)
	}
}
