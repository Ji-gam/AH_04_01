// 웹푸시 서비스워커. 탭/브라우저가 닫혀있어도 서버가 보낸 push 메시지를 받아 OS 알림으로
// 띄우는 역할을 한다 - 지금 있던 Notification API(포그라운드 폴링, AlarmPage.tsx의
// checkAndFire)와 달리, 진짜 백그라운드 알림은 이 서비스워커를 거쳐야만 가능하다.

self.addEventListener("push", (event) => {
  let payload = { title: "복약 알림", body: "복약 시간이에요!" };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch {
    // 서버가 JSON이 아닌 형태로 보냈으면 기본 문구로 대체 - 알림 자체는 뜨게 한다.
  }

  // actions/data가 있으면(복약알림 본인 몫 - push_service.py의 snooze_source) "30분/1시간
  // 후 다시" 버튼을 붙인다. 없으면(가족에게 전달된 사본, 습관 달성 알림 등) 그냥 텍스트만.
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      actions: payload.actions,
      data: payload.data,
    }),
  );
});

// 액션 버튼(스누즈) 클릭 시 로그인 세션 없이 백엔드에 재발송을 예약한다 - 서비스워커는 앱이
// 완전히 꺼져있어도 실행되지만 페이지 메모리에만 있는 JWT엔 접근할 수 없다(app/dtos/push.py의
// SnoozeRequest 주석 참고). 그 외(본문 클릭 등)는 기존대로 앱 포커스/열기만 한다.
self.addEventListener("notificationclick", (event) => {
  const { action, notification } = event;
  notification.close();

  if (action === "snooze_30" || action === "snooze_60") {
    const minutes = action === "snooze_30" ? 30 : 60;
    const { profile_id, source_type, source_id } = notification.data || {};
    if (profile_id && source_type && source_id) {
      event.waitUntil(
        fetch("/api/v1/push/snooze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile_id, source_type, source_id, minutes }),
        }).catch(() => {
          // 오프라인 등으로 실패해도 알림 자체는 이미 닫혔다 - 조용히 무시.
        }),
      );
    }
    return;
  }

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow("/alarms");
      return undefined;
    }),
  );
});
