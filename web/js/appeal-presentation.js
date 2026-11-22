const replyDateFormat = (timeZone) => new Intl.DateTimeFormat('ru-RU', {
  dateStyle: 'short', timeStyle: 'short', timeZone,
});
const moscowDate = replyDateFormat('Europe/Moscow');
const savedWallTime = replyDateFormat('UTC');

export const appealReplyAttribution = (issue) => {
  const byline = document.createElement('small');
  byline.className = 'appeal-reply-attribution';
  byline.textContent = issue.reply_author_display_name?.trim() || 'Администратор';
  if (issue.replied_at) {
    // The existing HTTP contract can return a timestamp without an offset.
    const zoned = /(?:Z|[+-]\d{2}:\d{2})$/i.test(issue.replied_at);
    const date = new Date(zoned ? issue.replied_at : issue.replied_at + 'Z');
    if (Number.isFinite(date.getTime())) {
      const time = document.createElement('time');
      time.dateTime = issue.replied_at;
      time.textContent = zoned ? moscowDate.format(date) + ' МСК' : savedWallTime.format(date);
      byline.append(' · ', time);
    }
  }
  return byline;
};
